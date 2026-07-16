#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging

from datetime import datetime
from typing import Any, Dict, List

from croniter import croniter

from backend.app.coulddrive.crud.crud_filesync import sync_config_dao, sync_task_dao
from backend.app.coulddrive.service.filesync_service import file_sync_service
from backend.app.task.celery import celery_app
from backend.app.task.tasks.filesync.debug_logger import (
    log_task_dispatch,
    log_task_end,
    log_task_skipped,
    log_task_start,
)
from backend.database.db import async_db_session
from backend.database.redis import redis_client
from backend.utils.timezone import timezone

logger = logging.getLogger(__name__)

# Redis 锁相关常量
FILESYNC_EXEC_LOCK_PREFIX = 'filesync:exec_lock:'
FILESYNC_EXEC_LOCK_TTL = 600  # 锁过期时间 10 分钟，防止异常退出后死锁


@celery_app.task(name='filesync:check_and_execute_cron_tasks')
async def check_and_execute_filesync_cron_tasks() -> Dict[str, Any]:
    """
    检查并执行文件同步定时任务

    扫描所有启用的同步配置，检查其cron字段，
    如果到了执行时间则触发同步任务

    :return: 执行结果统计
    """
    result = {'checked_configs': 0, 'executed_tasks': 0, 'failed_tasks': 0, 'skipped_tasks': 0, 'execution_details': []}

    # 用于收集详细信息的临时列表
    temp_details = []

    try:
        async with async_db_session() as db:
            # 获取所有启用的同步配置
            enabled_configs = await sync_config_dao.get_enabled_configs(db)
            result['checked_configs'] = len(enabled_configs)

            current_time = timezone.now()

            for config in enabled_configs:
                try:
                    # 检查是否有cron表达式
                    if not config.cron:
                        result['skipped_tasks'] += 1
                        temp_details.append({
                            'config_id': config.id,
                            'status': 'skipped',
                            'reason': '没有设置cron表达式',
                        })
                        continue

                    # 检查任务是否过期
                    end_time = datetime.fromisoformat(str(config.end_time)) if config.end_time else None
                    if end_time and current_time > end_time:
                        result['skipped_tasks'] += 1
                        temp_details.append({'config_id': config.id, 'status': 'skipped', 'reason': '任务已过期'})
                        continue

                    # 验证cron表达式
                    if not _is_valid_cron_expression(config.cron):
                        result['failed_tasks'] += 1
                        temp_details.append({'config_id': config.id, 'status': 'failed', 'reason': 'cron表达式无效'})
                        continue

                    # 检查是否到了执行时间
                    should_execute = _should_execute_now(config.cron, config.last_sync, current_time)

                    if not should_execute:
                        result['skipped_tasks'] += 1
                        temp_details.append({'config_id': config.id, 'status': 'skipped', 'reason': '未到执行时间'})
                        continue

                    # 派发前检查 Redis 锁，避免重复派发
                    lock_key = f'{FILESYNC_EXEC_LOCK_PREFIX}{config.id}'
                    if await redis_client.exists(lock_key):
                        result['skipped_tasks'] += 1
                        temp_details.append({
                            'config_id': config.id,
                            'status': 'skipped',
                            'reason': '已有任务正在执行（Redis 锁存在）',
                        })
                        log_task_skipped(config.id, f'Redis 锁存在, key={lock_key}')
                        continue

                    # 执行同步任务
                    # 【核心修复】：不要直接 execute 阻塞，否则共用一个 DB Session 必断开连接！
                    # 应交给专门处理单条配置的 Celery task 去执行
                    async_result = execute_filesync_task_by_config_id.delay(config.id)
                    celery_task_id = async_result.id if async_result else 'unknown'

                    # 调试日志
                    log_task_dispatch('execute_filesync_task_by_config_id', config.id, celery_task_id)

                    result['executed_tasks'] += 1
                    temp_details.append({
                        'config_id': config.id,
                        'status': 'dispatched',
                        'reason': '已推送至后台队列异步执行',
                    })
                    logger.info(f'配置 {config.remark} 的同步任务已成功派发到 Celery 队列')

                except Exception as e:
                    logger.error(f'处理配置 {config.id} 时发生错误: {str(e)}')
                    result['failed_tasks'] += 1
                    temp_details.append({'config_id': config.id, 'status': 'error', 'error': str(e)})

    except Exception as e:
        logger.error(f'检查文件同步定时任务时发生错误: {str(e)}')
        result['error'] = str(e)

    # 合并相同状态和原因的配置
    result['execution_details'] = _merge_execution_details(temp_details)

    return _compact_filesync_result(result)


@celery_app.task(name='filesync:execute_task_by_config_id', bind=True)
async def execute_filesync_task_by_config_id(self, config_id: int) -> Dict[str, Any]:
    """
    根据配置ID执行单个文件同步任务

    :param config_id: 同步配置ID
    :return: 执行结果
    """
    celery_task_id = self.request.id
    lock_key = f'{FILESYNC_EXEC_LOCK_PREFIX}{config_id}'

    try:
        # 原子性分布式锁：SET NX + EX，保证同一 config_id 只有一个 worker 在执行
        lock_acquired = await redis_client.set(lock_key, celery_task_id, nx=True, ex=FILESYNC_EXEC_LOCK_TTL)
        if not lock_acquired:
            logger.warning(f'配置 {config_id} 获取 Redis 锁失败，已有任务正在执行，跳过本次')
            log_task_skipped(config_id, f'Redis 锁竞争失败, celery_id={celery_task_id}')
            return {
                'success': True,
                'config_id': config_id,
                'skipped': True,
                'message': '已有正在执行的同步任务（Redis 锁），跳过本次执行',
            }

        try:
            async with async_db_session() as db:
                # 二级防护：数据库幂等性检查
                if await sync_task_dao.has_running_task(db, config_id=config_id):
                    logger.warning(f'配置 {config_id} 已有正在运行的同步任务，跳过本次执行')
                    log_task_skipped(config_id, f'已有 running 任务, celery_id={celery_task_id}')
                    return {
                        'success': True,
                        'config_id': config_id,
                        'skipped': True,
                        'message': '已有正在运行的同步任务，跳过本次执行',
                    }

                log_task_start(config_id, task_id=None, celery_task_id=celery_task_id)

                result = await file_sync_service.execute_sync_by_config_id(config_id, db)

                if not result.get('success'):
                    logger.error(f'配置 {config_id} 同步任务执行失败: {result.get("error")}')

                log_task_end(
                    config_id,
                    task_id=result.get('task_id'),
                    success=result.get('success', False),
                    stats=result.get('stats'),
                    error=result.get('error'),
                )

                return _compact_filesync_result(result)

        finally:
            # 无论成功或失败，释放 Redis 锁
            await redis_client.delete(lock_key)

    except Exception as e:
        # 异常时也要尝试释放锁
        try:
            await redis_client.delete(lock_key)
        except Exception:
            pass
        error_msg = f'执行配置 {config_id} 同步任务时发生错误: {str(e)}'
        logger.error(error_msg)
        log_task_end(config_id, task_id=None, success=False, error=error_msg)
        return {'success': False, 'error': error_msg, 'config_id': config_id}


def _compact_filesync_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """
    压缩文件同步任务返回，避免 Celery 成功日志输出明细。

    :param result: 原始文件同步结果
    :return:
    """
    compact_result = {
        key: value
        for key, value in result.items()
        if key not in {'execution_details', 'stats'}
    }
    stats = result.get('stats')
    if isinstance(stats, dict):
        compact_result['stats'] = {
            key: value
            for key, value in stats.items()
            if key not in {'pending_task_items', 'transferred_files_info'}
        }
    return compact_result


@celery_app.task(name='filesync:get_configs_with_cron')
async def get_filesync_configs_with_cron() -> List[Dict[str, Any]]:
    """
    获取所有设置了cron表达式的同步配置

    :return: 配置列表
    """
    try:
        async with async_db_session() as db:
            enabled_configs = await sync_config_dao.get_enabled_configs(db)

            configs_with_cron = []
            for config in enabled_configs:
                if config.cron:
                    config_info = {
                        'id': config.id,
                        'remark': config.remark,
                        'cron': config.cron,
                        'last_sync': str(config.last_sync) if config.last_sync else None,
                        'end_time': str(config.end_time) if config.end_time else None,
                        'src_path': config.src_path,
                        'dst_path': config.dst_path,
                        'type': config.type,
                        'is_valid_cron': _is_valid_cron_expression(config.cron),
                    }

                    # 计算下次执行时间
                    if config_info['is_valid_cron']:
                        try:
                            cron = croniter(config.cron, timezone.now())
                            next_run = cron.get_next(datetime)
                            config_info['next_run'] = next_run.isoformat()
                        except Exception:
                            config_info['next_run'] = None
                    else:
                        config_info['next_run'] = None

                    configs_with_cron.append(config_info)

            return configs_with_cron

    except Exception as e:
        logger.error(f'获取cron配置时发生错误: {str(e)}')
        return []


def _is_valid_cron_expression(cron_expr: str) -> bool:
    """
    验证cron表达式是否有效

    :param cron_expr: cron表达式
    :return: 是否有效
    """
    try:
        croniter(cron_expr)
        return True
    except Exception:
        return False


def _should_execute_now(cron_expr: str, last_sync: Any | None, current_time: datetime) -> bool:
    """
    判断是否应该在当前时间执行任务

    :param cron_expr: cron表达式
    :param last_sync: 上次同步时间
    :param current_time: 当前时间
    :return: 是否应该执行
    """
    try:
        # 基于当前时间创建 croniter
        cron = croniter(cron_expr, current_time)

        # 获取当前时间之前的最近一次应该执行的时间
        prev_execution_time = cron.get_prev(datetime)

        # 计算当前检查时间与最近执行时间的差距（分钟）
        # 如果差距在合理范围内（比如5分钟内），认为是在执行窗口内
        time_diff_minutes = (current_time - prev_execution_time).total_seconds() / 60

        # 定义执行窗口：最近执行时间后的5分钟内都算有效执行窗口
        execution_window_minutes = 5

        # 检查是否在执行窗口内
        in_execution_window = 0 <= time_diff_minutes <= execution_window_minutes

        # 从未同步过的情况：只有在执行窗口内才执行
        if last_sync is None:
            return in_execution_window

        # 已有同步历史的情况：检查上次同步时间是否早于最近的执行时间
        last_sync_dt = datetime.fromisoformat(str(last_sync)) if last_sync else None
        if last_sync_dt and last_sync_dt < prev_execution_time and in_execution_window:
            return True

        return False

    except Exception as e:
        logger.error(f'解析cron表达式 {cron_expr} 时发生错误: {str(e)}')
        return False


def _merge_execution_details(details: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    合并相同状态和原因的执行详情

    :param details: 原始执行详情列表
    :return: 合并后的执行详情列表
    """
    if not details:
        return []

    # 用于分组的字典，key为(status, reason/error)，value为配置ID列表和其他信息
    groups = {}

    for detail in details:
        status = detail.get('status')

        # 根据状态确定分组的key
        if status in ['skipped', 'failed'] and 'reason' in detail:
            # 对于有reason的情况，使用(status, reason)作为key
            group_key = (status, detail.get('reason'))
        elif status == 'failed' and 'error' in detail:
            # 对于有error的情况，使用(status, error)作为key
            group_key = (status, detail.get('error'))
        else:
            # 对于success等其他情况，每个配置单独一条记录
            group_key = (status, detail.get('config_id'))

        if group_key not in groups:
            groups[group_key] = {'config_ids': [], 'detail': detail.copy()}

        groups[group_key]['config_ids'].append(detail.get('config_id'))

    # 生成合并后的结果
    merged_details = []
    for (status, reason_or_error), group_data in groups.items():
        config_ids = group_data['config_ids']
        detail = group_data['detail']

        if len(config_ids) > 1:
            # 多个配置ID，合并显示
            detail['config_id'] = config_ids
        else:
            # 单个配置ID，保持原样
            detail['config_id'] = config_ids[0]

        merged_details.append(detail)

    # 按状态排序：success -> failed -> error -> skipped
    status_order = {'success': 1, 'failed': 2, 'error': 3, 'skipped': 4}
    merged_details.sort(key=lambda x: status_order.get(x.get('status'), 5))

    return merged_details
