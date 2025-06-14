#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging
from datetime import datetime
from typing import Dict, Any, List

from croniter import croniter

from backend.app.coulddrive.crud.crud_filesync import sync_config_dao
from backend.app.coulddrive.service.filesync_service import file_sync_service
from backend.app.task.celery import celery_app
from backend.database.db import async_db_session

logger = logging.getLogger(__name__)


@celery_app.task(name='check_and_execute_filesync_cron_tasks')
async def check_and_execute_filesync_cron_tasks() -> Dict[str, Any]:
    """
    检查并执行文件同步定时任务
    
    扫描所有启用的同步配置，检查其cron字段，
    如果到了执行时间则触发同步任务
    
    :return: 执行结果统计
    """
    try:
        result = await _check_and_execute_filesync_cron_tasks()
        # logger.info(f"定时任务检查完成: 检查 {result['checked_configs']} 个配置，"
        #            f"执行 {result['executed_tasks']} 个，"
        #            f"失败 {result['failed_tasks']} 个，"
        #            f"跳过 {result['skipped_tasks']} 个")
        return result
            
    except Exception as e:
        logger.error(f"定时任务检查失败: {str(e)}")
        return {
            "checked_configs": 0,
            "executed_tasks": 0,
            "failed_tasks": 0,
            "skipped_tasks": 0,
            "execution_details": [],
            "error": str(e)
        }


async def _check_and_execute_filesync_cron_tasks() -> Dict[str, Any]:
    """
    检查并执行文件同步定时任务的异步实现
    
    :return: 执行结果统计
    """
    result = {
        "checked_configs": 0,
        "executed_tasks": 0,
        "failed_tasks": 0,
        "skipped_tasks": 0,
        "execution_details": []
    }
    
    try:
        async with async_db_session() as db:
            # 获取所有启用的同步配置
            enabled_configs = await sync_config_dao.get_enabled_configs(db)
            result["checked_configs"] = len(enabled_configs)
            
            current_time = datetime.now()
            
            for config in enabled_configs:
                try:
                    # 检查是否有cron表达式
                    if not config.cron:
                        result["skipped_tasks"] += 1
                        result["execution_details"].append({
                            "config_id": config.id,
                            "status": "skipped",
                            "reason": "没有设置cron表达式"
                        })
                        continue
                    
                    # 检查任务是否过期
                    if config.end_time and current_time > config.end_time:
                        result["skipped_tasks"] += 1
                        result["execution_details"].append({
                            "config_id": config.id,
                            "status": "skipped",
                            "reason": "任务已过期"
                        })
                        continue
                    
                    # 验证cron表达式
                    if not _is_valid_cron_expression(config.cron):
                        result["failed_tasks"] += 1
                        result["execution_details"].append({
                            "config_id": config.id,
                            "status": "failed",
                            "reason": "cron表达式无效"
                        })
                        continue
                    
                    # 检查是否到了执行时间
                    should_execute = _should_execute_now(config.cron, config.last_sync, current_time)
                    
                    if not should_execute:
                        result["skipped_tasks"] += 1
                        result["execution_details"].append({
                            "config_id": config.id,
                            "status": "skipped",
                            "reason": "未到执行时间"
                        })
                        continue
                    
                    # logger.info(f"执行配置 {config.id} ({config.remark}) 的同步任务")
                    
                    # 执行同步任务
                    sync_result = await file_sync_service.execute_sync_by_config_id(config.id, db)
                    
                    if sync_result.get("success"):
                        result["executed_tasks"] += 1
                        result["execution_details"].append({
                            "config_id": config.id,
                            "status": "success",
                            "task_id": sync_result.get("task_id"),
                            "stats": sync_result.get("stats"),
                            "elapsed_time": sync_result.get("elapsed_time")
                        })
                        logger.info(f"配置 {config.remark} 执行成功")
                    else:
                        result["failed_tasks"] += 1
                        result["execution_details"].append({
                            "config_id": config.id,
                            "status": "failed",
                            "error": sync_result.get("error"),
                            "task_id": sync_result.get("task_id")
                        })
                        logger.error(f"配置 {config.id} 同步任务执行失败: {sync_result.get('error')}")
                
                except Exception as e:
                    logger.error(f"处理配置 {config.id} 时发生错误: {str(e)}")
                    result["failed_tasks"] += 1
                    result["execution_details"].append({
                        "config_id": config.id,
                        "status": "error",
                        "error": str(e)
                    })
    
    except Exception as e:
        logger.error(f"检查文件同步定时任务时发生错误: {str(e)}")
        result["error"] = str(e)
    
    return result


@celery_app.task(name='execute_filesync_task_by_config_id')
async def execute_filesync_task_by_config_id(config_id: int) -> Dict[str, Any]:
    """
    根据配置ID执行单个文件同步任务
    
    :param config_id: 同步配置ID
    :return: 执行结果
    """
    try:
        return await _execute_filesync_task_by_config_id(config_id)
    except Exception as e:
        logger.error(f"执行配置 {config_id} 同步任务失败: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "config_id": config_id
        }


async def _execute_filesync_task_by_config_id(config_id: int) -> Dict[str, Any]:
    """
    根据配置ID执行单个文件同步任务的异步实现
    
    :param config_id: 同步配置ID
    :return: 执行结果
    """
    try:
        async with async_db_session() as db:
            result = await file_sync_service.execute_sync_by_config_id(config_id, db)
            
            if result.get("success"):
                pass
            else:
                logger.error(f"配置 {config_id} 同步任务执行失败: {result.get('error')}")
            
            return result
    
    except Exception as e:
        error_msg = f"执行配置 {config_id} 同步任务时发生错误: {str(e)}"
        logger.error(error_msg)
        return {
            "success": False,
            "error": error_msg,
            "config_id": config_id
        }


@celery_app.task(name='get_filesync_configs_with_cron')
async def get_filesync_configs_with_cron() -> List[Dict[str, Any]]:
    """
    获取所有设置了cron表达式的同步配置
    
    :return: 配置列表
    """
    try:
        return await _get_filesync_configs_with_cron()
    except Exception as e:
        logger.error(f"获取cron配置列表失败: {str(e)}")
        return []


async def _get_filesync_configs_with_cron() -> List[Dict[str, Any]]:
    """
    获取所有设置了cron表达式的同步配置的异步实现
    
    :return: 配置列表
    """
    try:
        async with async_db_session() as db:
            enabled_configs = await sync_config_dao.get_enabled_configs(db)
            
            configs_with_cron = []
            for config in enabled_configs:
                if config.cron:
                    config_info = {
                        "id": config.id,
                        "remark": config.remark,
                        "cron": config.cron,
                        "last_sync": config.last_sync.isoformat() if config.last_sync else None,
                        "end_time": config.end_time.isoformat() if config.end_time else None,
                        "src_path": config.src_path,
                        "dst_path": config.dst_path,
                        "type": config.type,
                        "is_valid_cron": _is_valid_cron_expression(config.cron)
                    }
                    
                    # 计算下次执行时间
                    if config_info["is_valid_cron"]:
                        try:
                            cron = croniter(config.cron, datetime.now())
                            next_run = cron.get_next(datetime)
                            config_info["next_run"] = next_run.isoformat()
                        except Exception:
                            config_info["next_run"] = None
                    else:
                        config_info["next_run"] = None
                    
                    configs_with_cron.append(config_info)
            
            return configs_with_cron
    
    except Exception as e:
        logger.error(f"获取cron配置时发生错误: {str(e)}")
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


def _should_execute_now(cron_expr: str, last_sync: datetime | None, current_time: datetime) -> bool:
    """
    判断是否应该在当前时间执行任务
    
    :param cron_expr: cron表达式
    :param last_sync: 上次同步时间
    :param current_time: 当前时间
    :return: 是否应该执行
    """
    try:
        # 从未同步过，立即执行
        if last_sync is None:
            return True
        
        # 根据cron表达式计算下次执行时间
        cron = croniter(cron_expr, last_sync)
        next_execution_time = cron.get_next(datetime)
        
        # 检查是否到了执行时间
        if current_time >= next_execution_time:
            # 检查延迟是否在合理范围内（1小时）
            delay_seconds = (current_time - next_execution_time).total_seconds()
            if delay_seconds <= 3600:
                return True
            else:
                # 延迟过久，跳过本次执行
                logger.warning(f"执行时间延迟过久({delay_seconds:.1f}秒)，跳过本次执行")
                return False
        
        return False
    
    except Exception as e:
        logger.error(f"解析cron表达式 {cron_expr} 时发生错误: {str(e)}")
        return False 