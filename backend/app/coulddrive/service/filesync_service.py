#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import json
import logging
import time

from datetime import datetime
from types import SimpleNamespace
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.coulddrive.crud.crud_drive_account import drive_account_dao
from backend.app.coulddrive.crud.crud_filesync import sync_config_dao, sync_task_dao, sync_task_item_dao
from backend.app.coulddrive.schema.enum import DriveType, RecursionSpeed, SyncMethod
from backend.app.coulddrive.schema.file import (
    DiskTargetDefinition,
    ExclusionRuleDefinition,
    RenameParam,
    ShareSourceDefinition,
    TransferParam,
)
from backend.app.coulddrive.schema.filesync import (
    CreateSyncTaskItemParam,
    CreateSyncTaskParam,
    UpdateSyncConfigParam,
    UpdateSyncTaskParam,
)
from backend.app.coulddrive.service.coulddrive_service import CouldDriveService
from backend.app.coulddrive.service.filesync import stats as sync_stats
from backend.app.coulddrive.service.filesync.executor import FileSyncExecutor
from backend.app.coulddrive.service.filesync.local_guard import LocalSyncGuard
from backend.app.coulddrive.service.filesync.planner import (
    FolderSyncPlan,
    build_directory_sync_plan,
    build_target_delete_plan,
    build_transfer_file_info,
)
from backend.app.coulddrive.service.filesync.scanner import FileSyncScanner
from backend.app.coulddrive.service.rule_template_service import (
    ItemFilter,
    MatchTarget,
    RenameRule,
    parse_exclusion_rules,
    parse_rule_templates,
)
from backend.app.coulddrive.service.utils_service import (
    build_full_path,
    get_filename,
    get_parent_path,
    join_path,
)
from backend.app.task.tasks.filesync.debug_logger import (
    log_api_call,
    log_overwrite_scan,
    log_target_verify,
)
from backend.common.db_lock import DatabaseMutex
from backend.common.log import log
from backend.database.db import async_db_session
from backend.plugin.notify.service.notify_service import notify_service
from backend.utils.timezone import timezone

logger = logging.getLogger(__name__)


class FileSyncService:
    """
    文件同步服务（带详细任务项记录）

    核心方法：
    1. perform_sync() - 同步入口
    2. sync_with_have() - 目标存在时同步
    3. sync_without_have() - 目标不存在时同步
    4. list_dir() - 列出目录
    5. transfer_files() - 转存或同盘复制文件
    6. delete_files() - 删除文件（批量优势）
    7. create_directory() - 创建目录
    8. record_task_item() - 记录任务项
    """

    def __init__(self) -> None:
        """初始化同步服务"""
        self.logger = log
        self.scanner = FileSyncScanner(logger=self.logger)
        self.local_guard = LocalSyncGuard(
            logger=self.logger,
            list_dir=self.list_dir,
            record_task_item=self.record_task_item,
        )
        self.executor = FileSyncExecutor(
            logger=self.logger,
            check_cancel_requested=self._check_cancel_requested,
            record_task_item=self.record_task_item,
            update_transferred_file_ids=self._update_transferred_file_ids,
        )

    async def execute_sync_by_config_id(self, config_id: int, db: AsyncSession) -> dict[str, Any]:
        """
        根据配置ID执行同步任务 - 数据库操作入口

        :param config_id: 同步配置ID
        :param db: 数据库会话
        :return:
        """
        start_time = time.time()
        task_id = None
        sync_task = None
        config = None
        pending_task_items = []

        self.logger.info(f'[任务unknown] 开始执行同步任务，配置ID: {config_id}')

        try:
            # 验证配置
            config, error = await self._validate_config(db, config_id)
            if error:
                return error

            # 检查任务是否过期
            expired_result = self._check_task_expired(config, config_id)
            if expired_result:
                return expired_result

            # 获取网盘账户
            drive_account, error = await self._get_drive_account(db, config)
            if error:
                return error

            # 创建同步任务记录
            sync_task = await self._create_sync_task(db, config_id, config.created_by)
            task_id = sync_task.id

            # 更新配置的最后同步时间
            error = await self._update_config_last_sync(db, config, task_id, config_id)
            if error:
                return error

            # 准备同步参数
            sync_params = await self._prepare_sync_params(db, config, drive_account, task_id)

            # 执行同步（带锁）
            sync_result = await self._execute_sync_with_lock(
                db, config, drive_account, sync_params, task_id, start_time
            )
            if 'error' in sync_result and sync_result.get('early_return'):
                return sync_result

            # 检查是否在同步过程中被取消
            if await self._check_cancel_requested(db, task_id):
                return await self._handle_task_cancelled(
                    db,
                    task_id,
                    sync_task,
                    sync_result.get('stats', {}),
                    sync_result.get('stats', {}).get('pending_task_items', []),
                    start_time,
                    config_id,
                )

            # 处理同步结果
            stats_from_sync = sync_result.get('stats', {})
            pending_task_items = stats_from_sync.get('pending_task_items', [])
            elapsed_time = int(time.time() - start_time)

            if sync_result.get('success', False):
                # 执行重命名操作
                await self._handle_post_sync_rename(drive_account, sync_params, stats_from_sync, task_id, db)

                # 处理成功结果
                result = await self._handle_sync_success(
                    db, sync_task, stats_from_sync, pending_task_items, elapsed_time, task_id, config_id
                )

                # 有失败项时发送警告通知
                error_count = len(stats_from_sync.get('errors', []))
                if error_count > 0:
                    await self._notify(
                        title='文件同步部分失败',
                        config=config,
                        extra=(
                            f'任务ID: {task_id} | 耗时: {elapsed_time}秒\n'
                            f'转存: {stats_from_sync.get("files_transferred", 0)} 个 | 失败: {error_count} 个\n'
                            f'首个错误: {stats_from_sync["errors"][0][:200]}'
                        ),
                        tags='文件同步|部分失败',
                    )

                warning_count = len(stats_from_sync.get('warnings', []))
                if warning_count > 0:
                    await self._notify(
                        title='文件同步警告',
                        config=config,
                        extra=(
                            f'任务ID: {task_id} | 耗时: {elapsed_time}秒\n'
                            f'警告: {warning_count} 条\n'
                            f'首个警告: {stats_from_sync["warnings"][0][:200]}'
                        ),
                        tags='文件同步|警告',
                    )

                return result
            else:
                # 处理失败结果
                result = await self._handle_sync_failure(
                    db, sync_task, sync_result, stats_from_sync, pending_task_items, elapsed_time, task_id, config_id
                )

                # 发送同步失败通知
                if stats_from_sync.get('local_protection_skipped'):
                    notify_title = '文件同步保护性跳过'
                    notify_tags = '文件同步|保护跳过'
                else:
                    notify_title = '文件同步失败'
                    notify_tags = '文件同步|同步失败'

                await self._notify(
                    title=notify_title,
                    config=config,
                    extra=(
                        f'任务ID: {task_id} | 耗时: {elapsed_time}秒\n'
                        f'错误: {sync_result.get("error", "未知错误")[:300]}'
                    ),
                    tags=notify_tags,
                )

                return result

        except Exception as e:
            error_msg = f'执行同步任务时发生异常: {str(e)}'
            logger.error(f'[任务{task_id or "unknown"}] {error_msg}', exc_info=True)

            # 更新失败状态
            if task_id and sync_task:
                await self._update_task_on_exception(db, sync_task, pending_task_items, error_msg, start_time, task_id)

            # 发送异常通知（最严重）
            await self._notify(
                title='文件同步异常',
                config=config,
                extra=(
                    f'任务ID: {task_id or "unknown"} | 耗时: {int(time.time() - start_time)}秒\n异常: {str(e)[:300]}'
                ),
                tags='文件同步|异常',
            )

            return {
                'success': False,
                'task_id': task_id,
                'config_id': config_id,
                'error': error_msg,
                'elapsed_time': int(time.time() - start_time),
            }

    # ========== 私有方法：配置验证与准备 ==========

    async def _validate_config(self, db: AsyncSession, config_id: int) -> tuple[Any, dict | None]:
        """
        验证配置

        :param db: 数据库会话
        :param config_id: 同步配置 ID
        :return:
        """
        config, error_msg = await sync_config_dao.get_with_validation(db, config_id)
        if not config:
            self.logger.error(f'[任务unknown] 获取配置失败: {error_msg}')
            return None, {'success': False, 'error': error_msg, 'config_id': config_id, 'elapsed_time': 0}
        return config, None

    def _check_task_expired(self, config, config_id: int) -> dict | None:
        """
        检查任务是否过期

        :param config: 同步配置对象
        :param config_id: 同步配置 ID
        :return:
        """
        if not config.end_time:
            return None

        end_time_dt = (
            config.end_time if isinstance(config.end_time, datetime) else datetime.fromisoformat(str(config.end_time))
        )
        if timezone.now() > end_time_dt:
            self.logger.info(f'[任务unknown] 同步任务已过期，截止时间: {config.end_time}')
            return {
                'success': True,
                'message': f'同步任务已过期，截止时间: {config.end_time}',
                'config_id': config_id,
                'elapsed_time': 0,
                'stats': {'processed': 0, 'transferred': 0, 'deleted': 0, 'skipped': 0, 'errors': 0},
            }
        return None

    async def _get_drive_account(self, db: AsyncSession, config) -> tuple[Any, dict | None]:
        """
        获取网盘账户

        :param db: 数据库会话
        :param config: 同步配置对象
        :return:
        """
        drive_account = await drive_account_dao.get(db, config.user_id)
        if not drive_account or not drive_account.cookies:
            self.logger.error(f'[任务unknown] 网盘账户 {config.user_id} 不存在或cookies为空')
            return None, {
                'success': False,
                'error': f'网盘账户 {config.user_id} 不存在或cookies为空',
                'config_id': config.id,
                'elapsed_time': 0,
            }
        return drive_account, None

    async def _create_sync_task(self, db: AsyncSession, config_id: int, created_by: int) -> Any:
        """
        创建同步任务记录

        :param db: 数据库会话
        :param config_id: 同步配置 ID
        :param created_by: 创建者用户 ID
        :return:
        """
        task_params = CreateSyncTaskParam(
            config_id=config_id, start_time=timezone.now(), status='running', err_msg=None, task_num='{}', dura_time=0
        )
        sync_task = await sync_task_dao.create(db, obj_in=task_params, current_user_id=created_by)
        await db.commit()
        self.logger.info(f'[任务{sync_task.id}] 同步任务记录创建成功')
        return sync_task

    async def _update_config_last_sync(self, db: AsyncSession, config, task_id: int, config_id: int) -> dict | None:
        """
        更新配置的最后同步时间

        :param db: 数据库会话
        :param config: 同步配置对象
        :param task_id: 任务 ID
        :param config_id: 同步配置 ID
        :return:
        """
        try:
            config_update = UpdateSyncConfigParam(last_sync=timezone.now())
            await sync_config_dao.update(db, db_obj=config, obj_in=config_update)
            await db.commit()
            self.logger.info(f'[任务{task_id}] 配置 {config_id} 的last_sync已更新')
            return None
        except Exception as e:
            self.logger.error(f'[任务{task_id}] 更新配置last_sync失败: {e}')
            return {'success': False, 'error': f'更新last_sync失败: {e}', 'config_id': config_id, 'elapsed_time': 0}

    async def _prepare_sync_params(self, db: AsyncSession, config, drive_account, task_id: int) -> dict[str, Any]:
        """
        准备同步参数

        :param db: 数据库会话
        :param config: 同步配置对象
        :param drive_account: 网盘账户对象
        :param task_id: 任务 ID
        :return:
        """
        # 解析配置参数
        sync_method = self._parse_sync_method(config.method)
        recursion_speed = self._parse_recursion_speed(config.speed)

        # 解析规则模板
        exclude_rules, rename_rules = await parse_rule_templates(
            config.exclude_template_id, config.rename_template_id, db
        )

        # 解析源和目标定义
        src_meta = json.loads(config.src_meta) if config.src_meta else {}
        dst_meta = json.loads(config.dst_meta) if config.dst_meta else {}

        source_definition = ShareSourceDefinition(
            source_type=src_meta.get('source_type') or 'local',
            source_id=src_meta.get('source_id') or '',
            file_path=config.src_path,
            ext_params=src_meta.get('ext_params', {}),
        )

        target_definition = DiskTargetDefinition(file_path=config.dst_path, file_id=dst_meta.get('file_id', ''))

        account_key = f'filesync:{DriveType(drive_account.type).value}:{config.user_id}'

        return {
            'sync_method': sync_method,
            'recursion_speed': recursion_speed,
            'exclude_rules': exclude_rules,
            'rename_rules': rename_rules,
            'source_definition': source_definition,
            'target_definition': target_definition,
            'account_key': account_key,
        }

    # ========== 私有方法：同步执行 ==========

    async def _execute_sync_with_lock(
        self, db: AsyncSession, config, drive_account, sync_params: dict, task_id: int, start_time: float
    ) -> dict[str, Any]:
        """
        执行同步（带数据库锁）

        :param db: 数据库会话
        :param config: 同步配置对象
        :param drive_account: 网盘账户对象
        :param sync_params: 同步参数字典
        :param task_id: 任务 ID
        :param start_time: 开始时间戳
        :return:
        """
        self.logger.info(f'[任务{task_id}] 开始执行核心同步逻辑')

        perform_sync_kwargs = {
            'x_token': drive_account.cookies,
            'drive_type': DriveType(drive_account.type),
            'source_definition': sync_params['source_definition'],
            'target_definition': sync_params['target_definition'],
            'sync_method': sync_params['sync_method'],
            'recursion_speed': sync_params['recursion_speed'],
            'exclude_rules': sync_params['exclude_rules'],
            'max_depth': 100,
            'task_id': task_id,
            'db': db,
            'account_key': sync_params['account_key'],
        }

        if config.user_id and config.type:
            lock_key = f'filesync:{config.type}:{config.user_id}'
            self.logger.info(f'[任务{task_id}] 尝试获取文件同步锁: {lock_key}')
            try:
                async with DatabaseMutex(
                    async_db_session, lock_key, owner_id=str(task_id), max_wait_seconds=600, timeout_seconds=300
                ):
                    self.logger.info(f'[任务{task_id}] 成功获取文件同步锁')
                    sync_result = await self.perform_sync(**perform_sync_kwargs)
                self.logger.info(f'[任务{task_id}] 释放文件同步锁')
                return sync_result
            except TimeoutError:
                error_message = f'获取文件同步锁超时: {lock_key}'
                logger.warning(f'[任务{task_id}] {error_message}')
                return {
                    'success': False,
                    'error': error_message,
                    'config_id': config.id,
                    'task_id': task_id,
                    'elapsed_time': time.time() - start_time,
                    'early_return': True,
                }
        else:
            self.logger.info(f'[任务{task_id}] 无需文件同步锁，直接执行同步')
            return await self.perform_sync(**perform_sync_kwargs)

    async def _handle_post_sync_rename(
        self, drive_account, sync_params: dict, stats_from_sync: dict, task_id: int, db: AsyncSession
    ) -> None:
        """
        处理同步后的重命名操作

        :param drive_account: 网盘账户对象
        :param sync_params: 同步参数字典
        :param stats_from_sync: 同步统计信息
        :param task_id: 任务 ID
        :param db: 数据库会话
        :return:
        """
        rename_rules = sync_params.get('rename_rules')
        if not rename_rules:
            return

        self.logger.info(f'[任务{task_id}] 开始执行重命名操作，规则数量: {len(rename_rules)}')
        transferred_files_info = stats_from_sync.get('transferred_files_info', [])
        self.logger.info(f'[任务{task_id}] 待重命名文件数量: {len(transferred_files_info)}')

        # 创建服务实例用于重命名
        service = CouldDriveService(auth_data=drive_account.cookies, drive_type=DriveType(drive_account.type))

        await self.rename_files(
            service=service,
            transferred_files_info=transferred_files_info,
            rename_rules=rename_rules,
            task_id=task_id,
            db=db,
            account_key=sync_params['account_key'],
            stats=stats_from_sync,
        )

    # ========== 私有方法：结果处理 ==========

    async def _handle_sync_success(
        self,
        db: AsyncSession,
        sync_task,
        stats_from_sync: dict,
        pending_task_items: list,
        elapsed_time: int,
        task_id: int,
        config_id: int,
    ) -> dict[str, Any]:
        """
        处理同步成功

        :param db: 数据库会话
        :param sync_task: 同步任务对象
        :param stats_from_sync: 同步统计信息
        :param pending_task_items: 待记录的任务项列表
        :param elapsed_time: 耗时（秒）
        :param task_id: 任务 ID
        :param config_id: 同步配置 ID
        :return:
        """
        start_time_dt = sync_task.start_time if isinstance(sync_task.start_time, datetime) else None
        stats_for_json = sync_stats.prepare_stats_for_json(stats_from_sync)

        update_params = UpdateSyncTaskParam(
            status='completed',
            dura_time=elapsed_time,
            task_num=json.dumps(stats_for_json),
            err_msg=None,
            start_time=start_time_dt,
        )
        await sync_task_dao.update(db, db_obj=sync_task, obj_in=update_params)

        # 批量保存任务项
        await self._save_task_items(db, pending_task_items, task_id)
        await db.commit()

        self.logger.info(f'[任务{task_id}] 同步成功，总耗时: {elapsed_time}秒')

        return {
            'success': True,
            'task_id': task_id,
            'config_id': config_id,
            'stats': stats_from_sync,
            'elapsed_time': elapsed_time,
            'message': '同步任务执行成功',
        }

    async def _handle_sync_failure(
        self,
        db: AsyncSession,
        sync_task,
        sync_result: dict,
        stats_from_sync: dict,
        pending_task_items: list,
        elapsed_time: int,
        task_id: int,
        config_id: int,
    ) -> dict[str, Any]:
        """
        处理同步失败

        :param db: 数据库会话
        :param sync_task: 同步任务对象
        :param sync_result: 同步结果字典
        :param stats_from_sync: 同步统计信息
        :param pending_task_items: 待记录的任务项列表
        :param elapsed_time: 耗时（秒）
        :param task_id: 任务 ID
        :param config_id: 同步配置 ID
        :return:
        """
        error_msg = sync_result.get('error', '未知错误')
        start_time_dt = sync_task.start_time if isinstance(sync_task.start_time, datetime) else None
        stats_for_json = sync_stats.prepare_stats_for_json(stats_from_sync)

        update_params = UpdateSyncTaskParam(
            status='failed',
            dura_time=elapsed_time,
            err_msg=error_msg,
            task_num=json.dumps(stats_for_json),
            start_time=start_time_dt,
        )
        await sync_task_dao.update(db, db_obj=sync_task, obj_in=update_params)

        # 批量保存任务项
        await self._save_task_items(db, pending_task_items, task_id)
        await db.commit()

        self.logger.error(f'[任务{task_id}] 同步失败: {error_msg}，总耗时: {elapsed_time}秒')

        return {
            'success': False,
            'task_id': task_id,
            'config_id': config_id,
            'error': error_msg,
            'stats': stats_from_sync,
            'elapsed_time': elapsed_time,
        }

    async def _update_task_on_exception(
        self, db: AsyncSession, sync_task, pending_task_items: list, error_msg: str, start_time: float, task_id: int
    ) -> None:
        """
        异常时更新任务状态

        :param db: 数据库会话
        :param sync_task: 同步任务对象
        :param pending_task_items: 待记录的任务项列表
        :param error_msg: 错误信息
        :param start_time: 开始时间戳
        :param task_id: 任务 ID
        :return:
        """
        try:
            start_time_dt = sync_task.start_time if isinstance(sync_task.start_time, datetime) else None
            update_params = UpdateSyncTaskParam(
                status='failed', dura_time=int(time.time() - start_time), err_msg=error_msg, start_time=start_time_dt
            )
            await sync_task_dao.update(db, db_obj=sync_task, obj_in=update_params)

            # 保存已收集的任务项
            if pending_task_items:
                await self._save_task_items(db, pending_task_items, task_id)

            await db.commit()
        except Exception as e:
            self.logger.error(f'[任务{task_id}] 更新失败状态时出错: {e}')

    # ========== 私有方法：通知 ==========

    async def _notify(self, *, title: str, config=None, extra: str = '', tags: str = '') -> None:
        """
        发送同步相关通知（失败时不抛异常）

        :param title: 通知标题
        :param config: SyncConfig 对象，用于提取备注和路径
        :param extra: 补充内容
        :param tags: 通知标签
        :return:
        """
        try:
            lines = []
            if config:
                if getattr(config, 'remark', None):
                    lines.append(f'配置: {config.remark}')
                lines.append(f'路径: {config.src_path} → {config.dst_path}')
            if extra:
                lines.append(extra)

            await notify_service.send(
                title=title,
                content='\n'.join(lines),
                options={'tags': tags} if tags else None,
                source='filesync',
            )
        except Exception:
            pass

    # ========== 私有方法：工具方法 ==========

    async def _save_task_items(self, db: AsyncSession, pending_task_items: list, task_id: int) -> None:
        """
        批量保存任务项

        :param db: 数据库会话
        :param pending_task_items: 待保存的任务项列表
        :param task_id: 任务 ID
        :return:
        """
        if not pending_task_items:
            return

        self.logger.info(f'[任务{task_id}] 批量记录 {len(pending_task_items)} 个任务项')
        for item_param in pending_task_items:
            await sync_task_item_dao.create(db, obj_in=item_param)

    async def _check_cancel_requested(self, db: AsyncSession, task_id: int) -> bool:
        """
        检查是否请求取消任务

        :param db: 数据库会话
        :param task_id: 任务 ID
        :return:
        """
        sync_task = await sync_task_dao.get(db, task_id)
        if sync_task and sync_task.cancel_requested:
            self.logger.info(f'[任务{task_id}] 检测到取消请求')
            return True
        return False

    async def _handle_task_cancelled(
        self,
        db: AsyncSession,
        task_id: int,
        sync_task,
        stats: dict[str, Any],
        pending_task_items: list,
        start_time: float,
        config_id: int,
    ) -> dict[str, Any]:
        """
        处理任务被取消

        :param db: 数据库会话
        :param task_id: 任务 ID
        :param sync_task: 同步任务对象
        :param stats: 同步统计信息字典
        :param pending_task_items: 待记录的任务项列表
        :param start_time: 开始时间戳
        :param config_id: 同步配置 ID
        :return:
        """
        elapsed_time = int(time.time() - start_time)
        start_time_dt = sync_task.start_time if isinstance(sync_task.start_time, datetime) else None
        stats_for_json = sync_stats.prepare_stats_for_json(stats)

        update_params = UpdateSyncTaskParam(
            status='cancelled',
            dura_time=elapsed_time,
            err_msg='用户取消同步任务',
            task_num=json.dumps(stats_for_json),
            start_time=start_time_dt,
        )
        await sync_task_dao.update(db, db_obj=sync_task, obj_in=update_params)

        # 保存已处理的任务项
        await self._save_task_items(db, pending_task_items, task_id)
        await db.commit()

        self.logger.info(f'[任务{task_id}] 任务已取消，总耗时: {elapsed_time}秒')

        return {
            'success': False,
            'task_id': task_id,
            'config_id': config_id,
            'error': '用户取消同步任务',
            'stats': stats,
            'elapsed_time': elapsed_time,
            'cancelled': True,
        }

    def _parse_sync_method(self, method_str: str) -> str:
        """
        解析同步方式

        :param method_str: 同步方式字符串
        :return:
        """
        method_lower = method_str.lower() if method_str else ''

        if method_lower == SyncMethod.INCREMENTAL.value:
            return SyncMethod.INCREMENTAL.value
        elif method_lower == SyncMethod.FULL.value:
            return SyncMethod.FULL.value
        elif method_lower == SyncMethod.OVERWRITE.value:
            return SyncMethod.OVERWRITE.value
        else:
            self.logger.warning(f'未知的同步方式: {method_str}，使用默认增量同步')
            return SyncMethod.INCREMENTAL.value

    def _parse_recursion_speed(self, speed_value: int) -> RecursionSpeed:
        """
        解析递归速度

        :param speed_value: 速度值
        :return:
        """
        if speed_value == 1:
            return RecursionSpeed.SLOW
        elif speed_value == 2:
            return RecursionSpeed.FAST
        else:
            return RecursionSpeed.NORMAL

    def _apply_rename_rules(
        self,
        file_info: dict[str, Any],
        rename_rules: list[RenameRule] | None,
    ) -> dict[str, Any] | None:
        """
        在转存文件信息上应用重命名规则，返回带有新名称的文件信息，如果未重命名则返回 None

        :param file_info: 文件信息字典
        :param rename_rules: 重命名规则列表
        :return:
        """
        if not rename_rules:
            return None

        original_name = file_info.get('file_name', '')
        original_path = file_info.get('target_path', '') + original_name

        new_name = original_name
        new_path = original_path

        temp_item = SimpleNamespace(file_name=original_name, file_path=original_path)

        for rule in rename_rules:
            generated_value = rule.generate_new_path(temp_item)

            if generated_value:
                if rule.target_scope == MatchTarget.NAME:
                    new_name = generated_value
                    parent_path = get_parent_path(original_path)
                    new_path = build_full_path(parent_path, new_name)
                elif rule.target_scope == MatchTarget.PATH:
                    new_path = generated_value
                    new_name = get_filename(new_path)

                break

        if new_name != original_name or new_path != original_path:
            self.logger.info(
                f"[任务{file_info.get('task_id', 'unknown')}] 文件需要重命名: '{original_name}' -> '{new_name}'"
            )
            renamed_file_info = dict(file_info)
            renamed_file_info['file_name'] = new_name
            renamed_file_info['new_full_path'] = new_path
            return renamed_file_info

        self.logger.info(f'[任务{file_info.get("task_id", "unknown")}] 文件无需重命名')
        return None

    async def rename_file_item(
        self,
        service: CouldDriveService,
        file_info: dict[str, Any],
        task_id: int | None,
        db: AsyncSession | None = None,
        account_key: str | None = None,
        stats: dict[str, Any] | None = None,
        **kwargs,
    ) -> bool:
        """
        执行单个文件的重命名操作并记录任务项

        :param service: 网盘服务实例
        :param file_info: 文件信息字典
        :param task_id: 任务 ID
        :param db: 数据库会话
        :param account_key: 账户锁键
        :param stats: 同步统计信息字典
        :return:
        """
        original_name = file_info.get('original_name', file_info.get('file_name', ''))
        new_name = file_info.get('file_name', original_name)
        original_path = file_info.get('target_path', '')
        new_full_path = file_info.get('new_full_path', build_full_path(original_path, new_name))
        file_id = file_info.get('file_id', '')

        if not new_name or new_name == original_name:
            return True

        try:
            # 获取驱动类型
            drive_type = await service.get_drive_type()

            rename_params = RenameParam(
                drive_type=drive_type,
                file_id=file_id if file_id else None,
                file_path=build_full_path(original_path, original_name) if not file_id else None,
                file_name=original_name,
                parent_id=file_info.get('parent_id', file_info.get('file_id')),
                new_path=new_full_path,
                new_name=new_name,
            )

            renamed_file_info = await service.rename(params=rename_params)

            if renamed_file_info:
                self.logger.info(f"[任务{task_id}] 文件重命名成功: '{original_name}' -> '{new_name}'")
                if task_id and stats:
                    task_item = await self.record_task_item(
                        task_id,
                        'rename',
                        original_path,
                        original_path,
                        original_name,
                        file_info.get('file_size', 0),
                        'completed',
                        None,
                    )
                    stats['pending_task_items'].append(task_item)
                return True
            else:
                error_msg = f'文件重命名失败: API返回False, 源文件: {original_name}, 新名称: {new_name}'
                self.logger.error(f'[任务{task_id}] {error_msg}')
                if task_id and stats:
                    task_item = await self.record_task_item(
                        task_id,
                        'rename',
                        original_path,
                        original_path,
                        original_name,
                        file_info.get('file_size', 0),
                        'failed',
                        error_msg,
                    )
                    stats['pending_task_items'].append(task_item)
                return False
        except Exception as e:
            error_msg = f'执行重命名异常: {original_name} -> {new_name}, 错误: {e}'
            self.logger.error(f'[任务{task_id}] {error_msg}', exc_info=True)
            if task_id and stats:
                task_item = await self.record_task_item(
                    task_id,
                    'rename',
                    original_path,
                    original_path,
                    original_name,
                    file_info.get('file_size', 0),
                    'failed',
                    error_msg,
                )
                stats['pending_task_items'].append(task_item)
            return False

    async def perform_sync(
        self,
        x_token: str,
        drive_type: DriveType,
        source_definition: ShareSourceDefinition,
        target_definition: DiskTargetDefinition,
        sync_method: str,
        recursion_speed: RecursionSpeed = RecursionSpeed.NORMAL,
        exclude_rules: list[ExclusionRuleDefinition] | None = None,
        max_depth: int = 100,
        task_id: int | None = None,
        db: AsyncSession | None = None,
        account_key: str | None = None,
        **kwargs,
    ) -> dict[str, Any]:
        """
        执行同步 - 核心入口

        :param x_token: 认证令牌
        :param drive_type: 网盘类型
        :param source_definition: 源定义
        :param target_definition: 目标定义
        :param sync_method: 同步方式（incremental/full/overwrite）
        :param recursion_speed: 递归速度
        :param exclude_rules: 排除规则
        :param max_depth: 最大递归深度
        :param task_id: 任务 ID
        :param db: 数据库会话
        :param account_key: 账户锁键
        :return:
        """
        start_perform_sync_time = time.time()

        # 创建统一的服务实例，在整个同步过程中复用
        service = CouldDriveService(auth_data=x_token, drive_type=drive_type)

        # 解析过滤器
        item_filter = parse_exclusion_rules(exclude_rules) if exclude_rules else None

        stats = sync_stats.create_sync_stats(sync_method, start_perform_sync_time)

        try:
            # 根据同步方式选择处理逻辑
            if sync_method == 'overwrite':
                self.logger.info(f'[任务{task_id}] 采用覆盖同步模式')
                await self._handle_overwrite_sync(
                    service,
                    source_definition,
                    target_definition,
                    recursion_speed,
                    item_filter,
                    stats,
                    task_id,
                    db,
                    account_key=account_key,
                )
                self.logger.info(f'[任务{task_id}] 覆盖同步逻辑执行完成')
            else:
                self.logger.info(f'[任务{task_id}] 采用增量/完全同步模式')
                await self.sync_with_have(
                    service,
                    source_definition,
                    target_definition,
                    source_definition.file_path,
                    target_definition.file_path,
                    target_definition.file_id,
                    sync_method,
                    recursion_speed,
                    item_filter,
                    0,
                    max_depth,
                    stats,
                    task_id,
                    db,
                    account_key=account_key,
                )
                self.logger.info(f'[任务{task_id}] 增量/完全同步逻辑执行完成')

        except Exception as e:
            error_msg = f'同步失败: {str(e)}'
            self.logger.error(f'[任务{task_id or "unknown"}] {error_msg}', exc_info=True)
            sync_stats.add_error(stats, error_msg)

        sync_stats.finish_sync_stats(stats, start_perform_sync_time)
        return {'success': sync_stats.is_success(stats), 'stats': stats, 'error': sync_stats.first_error(stats)}

    async def _process_source_folder(
        self,
        service: CouldDriveService,
        source_definition: ShareSourceDefinition,
        target_definition: DiskTargetDefinition,
        folder_plan: FolderSyncPlan,
        target_parent_id: str | None,
        sync_method: str,
        recursion_speed: RecursionSpeed,
        item_filter: ItemFilter | None,
        current_depth: int,
        max_depth: int,
        stats: dict[str, Any],
        task_id: int | None,
        db: AsyncSession | None,
        processed_target_signatures: set[tuple[str, int]],
        account_key: str | None = None,
    ) -> None:
        """
        处理源目录中的子目录 - 递归进入子目录同步

        :param service: 网盘服务实例
        :param source_definition: 源定义
        :param target_definition: 目标定义
        :param folder_plan: 子目录同步计划
        :param target_parent_id: 目标父目录 ID
        :param sync_method: 同步方式
        :param recursion_speed: 递归速度
        :param item_filter: 过滤器
        :param current_depth: 当前递归深度
        :param max_depth: 最大递归深度
        :param stats: 同步统计信息字典
        :param task_id: 任务 ID
        :param db: 数据库会话
        :param processed_target_signatures: 已处理目标文件签名集合
        :param account_key: 账户锁键
        :return:
        """
        if not folder_plan.target_exists:
            # 目标目录没有这个目录，全量同步
            await self.sync_without_have(
                service,
                source_definition,
                target_definition,
                folder_plan.source_path,
                folder_plan.target_path,
                target_parent_id,
                sync_method,
                recursion_speed,
                item_filter,
                current_depth + 1,
                max_depth,
                stats,
                task_id,
                db,
                account_key=account_key,
            )
        else:
            # 目标目录有这个目录，继续递归
            await self.sync_with_have(
                service,
                source_definition,
                target_definition,
                folder_plan.source_path,
                folder_plan.target_path,
                folder_plan.target_file_id or '',
                sync_method,
                recursion_speed,
                item_filter,
                current_depth + 1,
                max_depth,
                stats,
                task_id,
                db,
                account_key=account_key,
            )

        # 标记目录为已处理（仅当目标中已存在时）
        if folder_plan.target_exists:
            processed_target_signatures.add((folder_plan.source_name, 0))

    async def _collect_full_sync_deletions(
        self,
        service: CouldDriveService,
        target_definition: DiskTargetDefinition,
        target_file_map: dict[str, Any],
        processed_target_signatures: set[tuple[str, int]],
        target_path: str,
        recursion_speed: RecursionSpeed,
        stats: dict[str, Any],
        task_id: int | None,
        db: AsyncSession | None,
        account_key: str | None = None,
    ) -> None:
        """
        全量同步时收集并删除目标目录中的多余文件

        :param service: 网盘服务实例
        :param target_definition: 目标定义
        :param target_file_map: 目标目录文件映射
        :param processed_target_signatures: 已处理目标文件签名集合
        :param target_path: 目标目录路径
        :param recursion_speed: 递归速度
        :param stats: 同步统计信息字典
        :param task_id: 任务 ID
        :param db: 数据库会话
        :param account_key: 账户锁键
        :return:
        """
        files_to_delete = build_target_delete_plan(target_file_map, processed_target_signatures, target_path)
        if files_to_delete:
            await self.executor.delete_files(
                service,
                target_definition,
                files_to_delete,
                recursion_speed,
                stats,
                task_id,
                db,
                account_key=account_key,
            )
            if db:
                await db.commit()

    async def sync_with_have(
        self,
        service: CouldDriveService,
        source_definition: ShareSourceDefinition,
        target_definition: DiskTargetDefinition,
        source_path: str,
        target_path: str,
        target_id: str | None,
        sync_method: str,
        recursion_speed: RecursionSpeed,
        item_filter: ItemFilter | None,
        current_depth: int,
        max_depth: int,
        stats: dict[str, Any],
        task_id: int | None,
        db: AsyncSession | None = None,
        account_key: str | None = None,
        **kwargs,
    ) -> None:
        """
        目标存在时的同步

        :param service: 网盘服务实例
        :param source_definition: 源定义
        :param target_definition: 目标定义
        :param source_path: 源目录路径
        :param target_path: 目标目录路径
        :param target_id: 目标目录 ID
        :param sync_method: 同步方式
        :param recursion_speed: 递归速度
        :param item_filter: 过滤器
        :param current_depth: 当前递归深度
        :param max_depth: 最大递归深度
        :param stats: 同步统计信息字典
        :param task_id: 任务 ID
        :param db: 数据库会话
        :param account_key: 账户锁键
        :return:
        """
        # 检查是否请求取消
        if task_id and db:
            if await self._check_cancel_requested(db, task_id):
                self.logger.info(f'[任务{task_id}] sync_with_have 检测到取消请求，停止处理')
                return

        if current_depth >= max_depth:
            self.logger.warning(f'[任务{task_id or "unknown"}] 达到最大递归深度 {max_depth}，停止递归: {source_path}')
            return

        try:
            source_file_map = await self.list_dir(
                service,
                source_path,
                True,
                item_filter,
                True,
                source_definition,
                task_id=task_id,
                db=db,
                account_key=account_key,
            )
            target_file_map = await self.list_dir(
                service,
                target_path,
                False,
                item_filter,
                False,
                target_definition,
                target_id,
                task_id,
                db,
                account_key=account_key,
            )
        except Exception as e:
            error_msg = f'扫描目录失败: {source_path} -> {target_path}, 错误: {str(e)}'
            self.logger.error(f'[任务{task_id or "unknown"}] {error_msg}', exc_info=True)
            sync_stats.add_error(stats, error_msg)
            return

        rename_ok = await self.local_guard.apply_same_parent_dir_renames(
            service,
            source_definition,
            target_definition,
            source_path,
            target_path,
            target_id,
            source_file_map,
            target_file_map,
            item_filter,
            stats,
            task_id,
            db,
            account_key=account_key,
        )
        if not rename_ok:
            return

        guard_ok = await self.local_guard.guard_directory_changes(
            service,
            source_definition,
            target_definition,
            source_path,
            target_path,
            target_id,
            source_file_map,
            target_file_map,
            sync_method,
            item_filter,
            stats,
            task_id,
            db,
            account_key=account_key,
        )
        if not guard_ok:
            return

        sync_plan = build_directory_sync_plan(source_file_map, target_file_map, source_path, target_path)
        stats['files_processed'] += sync_plan.files_processed
        stats['files_skipped'] += sync_plan.files_skipped

        # 处理源目录中的每个文件/目录
        for folder_plan in sync_plan.folders:
            await self._process_source_folder(
                service,
                source_definition,
                target_definition,
                folder_plan,
                target_id,
                sync_method,
                recursion_speed,
                item_filter,
                current_depth,
                max_depth,
                stats,
                task_id,
                db,
                sync_plan.processed_target_signatures,
                account_key=account_key,
            )

        # 批量转存当前目录下需要同步的文件
        if sync_plan.files_to_transfer:
            transfer_result = await self.transfer_files(
                service,
                source_definition,
                target_definition,
                sync_plan.files_to_transfer,
                recursion_speed,
                stats,
                task_id,
                db,
                account_key=account_key,
                current_target_id=target_id,
            )
            if not transfer_result:
                self.logger.warning(f'[任务{task_id or "unknown"}] 批量转存失败，跳过当前目录后续处理: {target_path}')
                return
            if db:
                await db.commit()

        # 全量同步时删除目标目录中多余的文件
        if sync_method == 'full':
            await self._collect_full_sync_deletions(
                service,
                target_definition,
                target_file_map,
                sync_plan.processed_target_signatures,
                target_path,
                recursion_speed,
                stats,
                task_id,
                db,
                account_key=account_key,
            )

    async def sync_without_have(
        self,
        service: CouldDriveService,
        source_definition: ShareSourceDefinition,
        target_definition: DiskTargetDefinition,
        source_path: str,
        target_path: str,
        target_id: str | None,
        sync_method: str,
        recursion_speed: RecursionSpeed,
        item_filter: ItemFilter | None,
        current_depth: int,
        max_depth: int,
        stats: dict[str, Any],
        task_id: int | None,
        db: AsyncSession | None = None,
        account_key: str | None = None,
        **kwargs,
    ) -> None:
        """
        目标不存在时的同步

        :param service: 网盘服务实例
        :param source_definition: 源定义
        :param target_definition: 目标定义
        :param source_path: 源目录路径
        :param target_path: 目标目录路径
        :param target_id: 目标目录 ID
        :param sync_method: 同步方式
        :param recursion_speed: 递归速度
        :param item_filter: 过滤器
        :param current_depth: 当前递归深度
        :param max_depth: 最大递归深度
        :param stats: 同步统计信息字典
        :param task_id: 任务 ID
        :param db: 数据库会话
        :param account_key: 账户锁键
        :return:
        """
        # 检查是否请求取消
        if task_id and db:
            if await self._check_cancel_requested(db, task_id):
                self.logger.info(f'[任务{task_id}] sync_without_have 检测到取消请求，停止处理')
                return

        if current_depth >= max_depth:
            self.logger.warning(f'[任务{task_id or "unknown"}] 达到最大递归深度 {max_depth}，停止递归: {source_path}')
            return

        # 创建目标目录
        dir_name = target_path.rstrip('/').split('/')[-1]

        created_dir_info = await self.executor.create_directory(
            service,
            target_definition,
            dir_name,
            task_id,
            parent_id=target_id or target_definition.file_id,  # 如果target_id为None，使用target_definition.file_id
        )

        # 如果创建失败，尝试查找已存在的目录
        if not created_dir_info:
            self.logger.warning(f'[任务{task_id}] 创建目录失败，尝试查找已存在的目录: {dir_name}')

            # 尝试在父目录中查找已存在的同名目录
            try:
                parent_id_for_search = target_id or target_definition.file_id
                existing_files = await self.list_dir(
                    service,
                    target_definition.file_path,
                    False,
                    None,
                    False,
                    target_definition,
                    parent_id_for_search,
                    task_id,
                    db,
                    account_key=account_key,
                )

                # 查找同名目录
                dir_name_with_slash = dir_name + '/'
                if dir_name_with_slash in existing_files:
                    existing_dir_info = existing_files[dir_name_with_slash]
                    if existing_dir_info.get('is_folder', False):
                        # 构造已存在目录的信息
                        from backend.app.coulddrive.schema.file import BaseFileInfo

                        created_dir_info = BaseFileInfo(
                            file_id=existing_dir_info.get('file_id'),
                            file_name=dir_name,
                            file_path=target_path,
                            is_folder=True,
                            file_size=0,
                        )
                        self.logger.info(
                            f'[任务{task_id}] 找到已存在的目录: {dir_name}, file_id: {created_dir_info.file_id}'
                        )
                    else:
                        error_msg = f'同名文件已存在，无法创建目录: {target_path}'
                        self.logger.error(f'[任务{task_id or "unknown"}] {error_msg}')
                        sync_stats.add_error(stats, error_msg)
                        return
                else:
                    error_msg = f'创建目录失败且未找到已存在目录: {target_path}'
                    self.logger.error(f'[任务{task_id or "unknown"}] {error_msg}')
                    sync_stats.add_error(stats, error_msg)
                    return

            except Exception as e:
                error_msg = f'查找已存在目录时发生错误: {target_path}, 错误: {str(e)}'
                self.logger.error(f'[任务{task_id or "unknown"}] {error_msg}')
                sync_stats.add_error(stats, error_msg)
                return

        stats['folder_created'] += 1

        # 记录创建目录的任务项
        if task_id and stats:
            task_item = await self.record_task_item(
                task_id, 'create', source_path, target_path, dir_name, 0, 'completed', None
            )
            stats['pending_task_items'].append(task_item)  # 添加到待记录列表
        # if db: await db.commit() # 每次创建目录后提交，现在统一在最上层提交

        # 更新target_definition为新创建的目录
        target_definition = DiskTargetDefinition(file_path=target_path, file_id=created_dir_info.file_id)

        try:
            # 获取源目录文件列表
            source_file_map = await self.list_dir(
                service,
                source_path,
                True,
                item_filter,
                True,
                source_definition,
                task_id=task_id,
                db=db,
                account_key=account_key,
            )
        except Exception as e:
            error_msg = f'扫描源目录失败: {source_path}, 错误: {str(e)}'
            self.logger.error(f'[任务{task_id or "unknown"}] {error_msg}', exc_info=True)
            sync_stats.add_error(stats, error_msg)
            return

        # 收集当前目录下的所有文件，用于批量转存
        files_to_transfer = []

        # 处理源目录中的每个文件/目录
        for file_name, file_info in source_file_map.items():
            if file_name.endswith('/'):
                # 递归处理子目录
                dir_name = file_name.rstrip('/')
                source_sub_path = join_path(source_path, dir_name, is_dir=True)
                target_sub_path = join_path(target_path, dir_name, is_dir=True)

                await self.sync_without_have(
                    service,
                    source_definition,
                    target_definition,
                    source_sub_path,
                    target_sub_path,
                    created_dir_info.file_id,
                    sync_method,
                    recursion_speed,
                    item_filter,
                    current_depth + 1,
                    max_depth,
                    stats,
                    task_id,
                    db,
                    account_key=account_key,
                )
            else:
                # 收集文件信息，用于批量转存
                stats['files_processed'] += 1  # 增加文件处理计数
                source_file_size = file_info.get('file_size', 0)
                files_to_transfer.append(
                    build_transfer_file_info(file_name, source_file_size, file_info, source_path, target_path)
                )

        # 批量转存当前目录下的所有文件
        if files_to_transfer:
            transfer_result = await self.transfer_files(
                service,
                source_definition,
                target_definition,
                files_to_transfer,
                recursion_speed,
                stats,
                task_id,
                db,
                account_key=account_key,
                current_target_id=target_definition.file_id,  # 使用新创建的目录ID
            )

            if not transfer_result:
                self.logger.warning(f'[任务{task_id or "unknown"}] 批量转存失败，跳过当前目录后续处理: {target_path}')
                return
            if db:
                await db.commit()

    async def list_dir(
        self,
        service: CouldDriveService,
        path: str,
        first_dst: bool,
        item_filter: ItemFilter | None,
        is_src: bool,
        definition,
        target_id: str | None = None,
        task_id: int | None = None,
        db: AsyncSession | None = None,
        **kwargs,
    ) -> dict[str, dict[str, Any]]:
        """
        列出目录

        :param service: 网盘服务实例
        :param path: 目录路径
        :param first_dst: 是否是第一个目标目录
        :param item_filter: 过滤器
        :param is_src: 是否是源目录
        :param definition: 目录定义
        :param target_id: 目标 ID
        :param task_id: 任务 ID
        :param db: 数据库会话
        :return:
        """
        return await self.scanner.list_dir(
            service,
            path,
            first_dst,
            item_filter,
            is_src,
            definition,
            target_id,
            task_id,
            db,
            **kwargs,
        )

    async def _build_transfer_request(
        self,
        service: CouldDriveService,
        source_definition: ShareSourceDefinition,
        target_definition: DiskTargetDefinition,
        files: list[dict[str, Any]],
        stats: dict[str, Any],
        task_id: int | None,
        current_target_id: str | None,
    ) -> TransferParam | None:
        """
        验证 file_id 并构建转存请求参数

        :param service: 网盘服务实例
        :param source_definition: 源定义
        :param target_definition: 目标定义
        :param files: 文件列表
        :param stats: 同步统计信息字典
        :param task_id: 任务 ID
        :param current_target_id: 当前目标目录 ID
        :return:
        """
        drive_type = await service.get_drive_type()

        # 提取并验证文件 ID 列表
        file_ids = []
        for file_info in files:
            file_id = file_info.get('file_id', '')
            if not file_id:
                error_msg = f'文件 {file_info.get("file_name", "")} 缺少file_id'
                self.logger.error(f'[任务{task_id or "unknown"}] {error_msg}')
                sync_stats.add_error(stats, error_msg)
                if task_id and stats:
                    task_item = await self.record_task_item(
                        task_id,
                        'copy',
                        file_info.get('source_path', ''),
                        file_info.get('target_path', ''),
                        file_info.get('file_name', ''),
                        file_info.get('file_size', 0),
                        'failed',
                        error_msg,
                    )
                    stats['pending_task_items'].append(task_item)
                return None
            file_ids.append(file_id)

        # 构建扩展参数：基础参数 + 文件特定参数
        ext_params = dict(source_definition.ext_params) if source_definition.ext_params else {}

        # 为每个文件构建扩展信息
        files_ext_info = []
        for file_info in files:
            file_ext_info = {
                'file_id': file_info.get('file_id'),
                'file_ext': {key: value for key, value in file_info.items() if key not in ['file_size', 'file_id']},
            }
            files_ext_info.append(file_ext_info)

        ext_params['files_ext_info'] = files_ext_info

        # 合并第一个文件的基础扩展信息（保持向后兼容）
        if files:
            first_file = files[0]
            for key, value in first_file.items():
                if key not in ['file_name', 'file_size', 'source_path', 'target_path', 'file_id']:
                    ext_params[key] = value

        first_file = files[0] if files else {}
        actual_target_id = current_target_id or target_definition.file_id

        return TransferParam(
            drive_type=drive_type,
            source_type=source_definition.source_type,
            source_id=source_definition.source_id,
            source_path=first_file.get('source_path', ''),
            target_path=first_file.get('target_path', target_definition.file_path),
            target_id=actual_target_id,
            file_ids=file_ids,
            ext=ext_params,
        )

    async def _update_transferred_file_ids(
        self,
        service: CouldDriveService,
        target_definition: DiskTargetDefinition,
        files: list[dict[str, Any]],
        actual_target_id: str | None,
        stats: dict[str, Any],
        task_id: int | None,
        db: AsyncSession | None,
        account_key: str | None = None,
    ) -> None:
        """
        转存成功后重新扫描目标目录，更新文件的 file_id

        :param service: 网盘服务实例
        :param target_definition: 目标定义
        :param files: 已转存的文件列表
        :param actual_target_id: 实际转存的目标目录 ID
        :param stats: 同步统计信息字典
        :param task_id: 任务 ID
        :param db: 数据库会话
        :param account_key: 账户锁键
        :return:
        """
        first_file = files[0] if files else {}
        actual_target_path = first_file.get('target_path', target_definition.file_path)

        current_target_file_map = await self.list_dir(
            service,
            actual_target_path,
            False,
            None,
            False,
            target_definition,
            actual_target_id,
            task_id,
            db,
            account_key=account_key,
        )

        for original_file_info in files:
            original_file_name = original_file_info.get('file_name', '')
            search_name = original_file_name + '/' if original_file_info.get('is_folder') else original_file_name

            if search_name in current_target_file_map:
                new_file_info = current_target_file_map[search_name]
                updated_file_info = dict(original_file_info)
                updated_file_info['file_id'] = new_file_info.get('file_id', original_file_info.get('file_id'))
                updated_file_info['parent_id'] = actual_target_id
                stats['transferred_files_info'].append(updated_file_info)
            else:
                stats['transferred_files_info'].append(original_file_info)

    # 单次转存最大文件数，超过此数量自动分批，避免夸克 41035 错误
    TRANSFER_BATCH_SIZE = 10

    async def transfer_files(
        self,
        service: CouldDriveService,
        source_definition: ShareSourceDefinition,
        target_definition: DiskTargetDefinition,
        files: list[dict[str, Any]],
        recursion_speed: RecursionSpeed,
        stats: dict[str, Any],
        task_id: int | None,
        db: AsyncSession | None = None,
        account_key: str | None = None,
        current_target_id: str | None = None,
        **kwargs,
    ) -> bool:
        """
        批量同步文件 - 超过 TRANSFER_BATCH_SIZE 时自动分批

        :param service: 网盘服务实例
        :param source_definition: 源定义
        :param target_definition: 目标定义
        :param files: 文件列表
        :param recursion_speed: 递归速度
        :param stats: 同步统计信息字典
        :param task_id: 任务 ID
        :param db: 数据库会话
        :param account_key: 账户锁键
        :param current_target_id: 当前目标目录 ID
        :return:
        """
        if not files:
            self.logger.info(f'[任务{task_id or "unknown"}] 没有文件需要同步，跳过批量同步。')
            return True

        # 检查是否请求取消
        if task_id and db:
            if await self._check_cancel_requested(db, task_id):
                self.logger.info(f'[任务{task_id}] transfer_files 检测到取消请求，停止同步')
                return False

        # 无需分批，直接调用单批次同步
        if len(files) <= self.TRANSFER_BATCH_SIZE:
            return await self._transfer_files_batch(
                service,
                source_definition,
                target_definition,
                files,
                recursion_speed,
                stats,
                task_id,
                db,
                account_key=account_key,
                current_target_id=current_target_id,
                **kwargs,
            )

        # 分批同步
        total_files = len(files)
        batch_size = self.TRANSFER_BATCH_SIZE
        total_batches = (total_files + batch_size - 1) // batch_size
        self.logger.info(
            f'[任务{task_id or "unknown"}] 文件数 {total_files} 超过单批限制 {batch_size}，'
            f'自动分 {total_batches} 批同步'
        )

        all_ok = True
        failed_batches = 0

        for batch_idx in range(total_batches):
            batch_start = batch_idx * batch_size
            batch_end = min(batch_start + batch_size, total_files)
            batch_files = files[batch_start:batch_end]

            self.logger.info(
                f'[任务{task_id or "unknown"}] 同步第 {batch_idx + 1}/{total_batches} 批，'
                f'文件 {batch_start + 1}-{batch_end}'
            )

            # 每批开始前检查取消
            if task_id and db:
                if await self._check_cancel_requested(db, task_id):
                    self.logger.info(f'[任务{task_id}] 分批同步检测到取消请求，停止处理')
                    return False

            batch_result = await self._transfer_files_batch(
                service,
                source_definition,
                target_definition,
                batch_files,
                recursion_speed,
                stats,
                task_id,
                db,
                account_key=account_key,
                current_target_id=current_target_id,
                **kwargs,
            )

            if not batch_result:
                self.logger.error(f'[任务{task_id or "unknown"}] 第 {batch_idx + 1}/{total_batches} 批同步失败')
                all_ok = False
                failed_batches += 1

        if failed_batches:
            self.logger.warning(f'[任务{task_id or "unknown"}] 分批同步完成，失败 {failed_batches}/{total_batches} 批')

        return all_ok

    async def _transfer_files_batch(
        self,
        service: CouldDriveService,
        source_definition: ShareSourceDefinition,
        target_definition: DiskTargetDefinition,
        files: list[dict[str, Any]],
        recursion_speed: RecursionSpeed,
        stats: dict[str, Any],
        task_id: int | None,
        db: AsyncSession | None = None,
        account_key: str | None = None,
        current_target_id: str | None = None,
        **kwargs,
    ) -> bool:
        """
        单批次同步文件（内部方法），不做分批

        :param service: 网盘服务实例
        :param source_definition: 源定义
        :param target_definition: 目标定义
        :param files: 文件列表（数量应 <= TRANSFER_BATCH_SIZE）
        :param recursion_speed: 递归速度
        :param stats: 同步统计信息字典
        :param task_id: 任务 ID
        :param db: 数据库会话
        :param account_key: 账户锁键
        :param current_target_id: 当前目标目录 ID
        :return:
        """
        try:
            if source_definition.source_type == 'local':
                return await self.executor.copy_local_files_batch(
                    service,
                    target_definition,
                    files,
                    recursion_speed,
                    stats,
                    task_id,
                    db,
                    current_target_id=current_target_id,
                )

            # 构建转存请求
            actual_target_id = current_target_id or target_definition.file_id
            params = await self._build_transfer_request(
                service,
                source_definition,
                target_definition,
                files,
                stats,
                task_id,
                current_target_id,
            )
            if params is None:
                return False

            self.logger.info(f'[任务{task_id}] 执行文件转存（已由上层获取账户锁）')
            transfer_result = await service.transfer_files(params=params)
            self.logger.info(f'[任务{task_id}] 转存API调用结果: {transfer_result}')

            # 调试日志
            log_api_call(
                task_id,
                'transfer',
                len(files),
                transfer_result,
                extra={
                    'target_path': target_definition.file_path,
                    'target_id': target_definition.file_id,
                    'files_sample': [f.get('file_name', '') for f in files[:10]],
                },
            )

            # 写后安静期，等待上游平台落盘/索引收敛
            await asyncio.sleep(2)

            if transfer_result:
                stats['files_transferred'] += len(files)
                self.logger.info(f'[任务{task_id or "unknown"}] 批量转存成功: {len(files)} 个文件')
                await self.executor.record_batch_task_items(files, task_id, stats, 'completed')
                await self._update_transferred_file_ids(
                    service,
                    target_definition,
                    files,
                    actual_target_id,
                    stats,
                    task_id,
                    db,
                    account_key=account_key,
                )
            else:
                error_msg = f'批量转存失败：API返回False，涉及 {len(files)} 个文件'
                self.logger.error(f'[任务{task_id or "unknown"}] {error_msg}')
                sync_stats.add_error(stats, error_msg)
                await self.executor.record_batch_task_items(files, task_id, stats, 'failed', error_msg)

            # 速度控制
            if recursion_speed == RecursionSpeed.SLOW:
                await asyncio.sleep(2)
            elif recursion_speed == RecursionSpeed.NORMAL:
                await asyncio.sleep(1)

            return transfer_result

        except Exception as e:
            error_msg = f'批量转存异常: {str(e)}'
            self.logger.error(f'[任务{task_id or "unknown"}] {error_msg}', exc_info=True)
            sync_stats.add_error(stats, error_msg)
            await self.executor.record_batch_task_items(files, task_id, stats, 'failed', error_msg)
            return False

    async def rename_files(
        self,
        service: CouldDriveService,
        transferred_files_info: list[dict[str, Any]],
        rename_rules: list[RenameRule] | None,
        task_id: int | None,
        db: AsyncSession | None = None,
        account_key: str | None = None,
        **kwargs,
    ) -> None:
        """
        在同步完成后执行文件重命名操作

        :param service: 网盘服务实例
        :param transferred_files_info: 成功转存的文件信息列表
        :param rename_rules: 重命名规则列表
        :param task_id: 任务 ID
        :param db: 数据库会话
        :param account_key: 账户锁键
        :return:
        """
        if not rename_rules or not transferred_files_info:
            self.logger.info(f'[任务{task_id}] 无重命名规则或无文件可重命名，跳过重命名操作。')
            return

        self.logger.info(
            f'[任务{task_id}] 开始执行重命名操作，共有 {len(transferred_files_info)} 个文件待检查，'
            f'重命名规则数量: {len(rename_rules)}'
        )
        files_to_rename = []

        # 遍历所有转存成功的文件，应用重命名规则
        for file_info in transferred_files_info:
            # _apply_rename_rules 返回的是一个包含新名称和路径的新字典，如果未重命名则返回 None
            renamed_info = self._apply_rename_rules(file_info, rename_rules)
            if renamed_info:
                # 存储原始名称用于任务记录
                renamed_info['original_name'] = file_info.get('file_name', '')
                files_to_rename.append(renamed_info)

        # 异步并行执行重命名操作
        if files_to_rename:
            self.logger.info(f'[任务{task_id}] 发现 {len(files_to_rename)} 个文件需要重命名')
            rename_tasks = [
                self.rename_file_item(service, file_info, task_id, db, account_key=account_key)
                for file_info in files_to_rename
            ]
            await asyncio.gather(*rename_tasks)
            if db:
                await db.commit()  # 每次批量重命名后提交
        else:
            self.logger.info(f'[任务{task_id}] 没有文件符合重命名条件')

    async def record_task_item(
        self,
        task_id: int,
        operation_type: str,
        src_path: str,
        dst_path: str,
        file_name: str,
        file_size: int,
        status: str,
        err_msg: str | None,
    ) -> CreateSyncTaskItemParam:
        """
        记录任务项

        :param task_id: 任务 ID
        :param operation_type: 操作类型（transfer/delete/create_dir）
        :param src_path: 源路径
        :param dst_path: 目标路径
        :param file_name: 文件名
        :param file_size: 文件大小
        :param status: 状态（pending/running/completed/failed/skipped）
        :param err_msg: 错误信息
        :return:
        """
        try:
            task_item_params = CreateSyncTaskItemParam(
                task_id=task_id,
                type=operation_type,
                src_path=src_path,
                dst_path=dst_path,
                file_name=file_name,
                file_size=file_size,
                status=status,
                err_msg=err_msg,
            )

            return task_item_params

        except Exception as e:
            self.logger.error(f'[任务{task_id}] 记录任务项失败: {e}', exc_info=True)
            # 如果记录任务项本身失败，返回一个带错误的任务项，或者让上层处理
            return CreateSyncTaskItemParam(
                task_id=task_id,
                type=operation_type,
                src_path=src_path,
                dst_path=dst_path,
                file_name=file_name,
                file_size=file_size,
                status='failed',
                err_msg=f'记录任务项失败: {e}',
            )

    async def _handle_overwrite_sync(
        self,
        service: CouldDriveService,
        source_definition: ShareSourceDefinition,
        target_definition: DiskTargetDefinition,
        recursion_speed: RecursionSpeed,
        item_filter: ItemFilter | None,
        stats: dict[str, Any],
        task_id: int | None,
        db: AsyncSession | None = None,
        account_key: str | None = None,
        **kwargs,
    ) -> None:
        """
        处理覆盖同步：先验证源目录可用，再删除目标目录所有文件，最后转存源目录所有内容

        :param service: 网盘服务实例
        :param source_definition: 源定义
        :param target_definition: 目标定义
        :param recursion_speed: 递归速度
        :param item_filter: 过滤器
        :param stats: 同步统计信息字典
        :param task_id: 任务 ID
        :param db: 数据库会话
        :param account_key: 账户锁键
        :return:
        """
        start_overwrite_sync_time = time.time()
        self.logger.info(
            f'[任务{task_id or "unknown"}] 开始覆盖同步: '
            f'源={source_definition.file_path}, 目标={target_definition.file_path}'
        )
        if self.local_guard.is_local_source(source_definition):
            self.local_guard.mark_protection_skip(
                stats,
                task_id,
                f'本地同步不自动执行覆盖模式，已跳过: {source_definition.file_path} -> {target_definition.file_path}',
            )
            return

        try:
            # 1. 先扫描源目录，验证源目录可用（防止源异常时误删目标数据）
            self.logger.info(f'[任务{task_id or "unknown"}] 覆盖同步：开始扫描源目录进行预验证')
            source_file_map = await self.list_dir(
                service,
                source_definition.file_path,
                True,
                item_filter,
                True,
                source_definition,
                task_id=task_id,
                db=db,
                account_key=account_key,
            )
            elapsed = time.time() - start_overwrite_sync_time
            self.logger.info(
                f'[任务{task_id or "unknown"}] 覆盖同步：源目录扫描完成，'
                f'耗时: {elapsed:.2f}秒，找到 {len(source_file_map)} 个文件/目录'
            )

            # 调试日志：记录源扫描结果
            log_overwrite_scan(
                task_id, 'source_scan', source_definition.file_path, len(source_file_map), list(source_file_map.keys())
            )

            if not source_file_map:
                error_msg = f'源目录为空或不存在: {source_definition.file_path}，跳过覆盖同步以保护目标数据'
                self.logger.error(f'[任务{task_id or "unknown"}] {error_msg}')
                sync_stats.add_error(stats, error_msg)
                elapsed = time.time() - start_overwrite_sync_time
                self.logger.info(
                    f'[任务{task_id or "unknown"}] 退出 _handle_overwrite_sync (源目录异常), 耗时: {elapsed:.2f}秒'
                )
                return

            # 2. 源目录验证通过，扫描目标目录
            self.logger.info(f'[任务{task_id or "unknown"}] 覆盖同步：开始扫描目标目录进行删除前准备')
            target_file_map = await self.list_dir(
                service,
                target_definition.file_path,
                False,
                item_filter,
                False,
                target_definition,
                target_definition.file_id,
                task_id,
                db,
                account_key=account_key,
            )
            elapsed = time.time() - start_overwrite_sync_time
            self.logger.info(
                f'[任务{task_id or "unknown"}] 覆盖同步：目标目录扫描完成，'
                f'耗时: {elapsed:.2f}秒，找到 {len(target_file_map)} 个文件/目录'
            )

            # 3. 删除目标目录所有文件
            if target_file_map:
                files_to_delete = []
                for file_name, file_info in target_file_map.items():
                    files_to_delete.append({
                        'file_name': file_name,
                        'file_size': file_info.get('file_size', 0),
                        'target_path': target_definition.file_path,
                        'file_id': file_info.get('file_id', ''),
                    })
                self.logger.info(
                    f'[任务{task_id or "unknown"}] 覆盖同步：开始批量删除 {len(files_to_delete)} 个文件/目录'
                )
                delete_start_time = time.time()
                await self.executor.delete_files(
                    service,
                    target_definition,
                    files_to_delete,
                    recursion_speed,
                    stats,
                    task_id,
                    db,
                    account_key=account_key,
                )
                self.logger.info(
                    f'[任务{task_id or "unknown"}] 覆盖同步：批量删除完成，耗时: {time.time() - delete_start_time:.2f}秒'
                )
                if db:
                    await db.commit()

                # 调试日志：删除后回查目标目录，确认是否真正清空
                try:
                    post_delete_map = await self.list_dir(
                        service,
                        target_definition.file_path,
                        False,
                        None,
                        False,
                        target_definition,
                        target_definition.file_id,
                        task_id,
                        db,
                        account_key=account_key,
                    )
                    log_overwrite_scan(
                        task_id,
                        'target_after_delete',
                        target_definition.file_path,
                        len(post_delete_map),
                        list(post_delete_map.keys()),
                    )
                except Exception as verify_err:
                    log_api_call(task_id, 'delete_verify_failed', 0, str(verify_err))
            else:
                self.logger.info(f'[任务{task_id or "unknown"}] 覆盖同步：目标目录为空，无需删除。')

            # 4. 转存源目录所有内容（source_file_map 已在步骤 1 获取）
            all_files_to_transfer = []
            for file_name, file_info in source_file_map.items():
                file_size = file_info.get('file_size', 0)
                all_files_to_transfer.append(
                    build_transfer_file_info(
                        file_name,
                        file_size,
                        file_info,
                        source_definition.file_path,
                        target_definition.file_path,
                    )
                )
                stats['files_processed'] += 1

            self.logger.info(f'[任务{task_id or "unknown"}] 覆盖同步：开始转存 {len(all_files_to_transfer)} 个项目')
            transfer_start_time = time.time()
            transfer_result = await self.transfer_files(
                service,
                source_definition,
                target_definition,
                all_files_to_transfer,
                recursion_speed,
                stats,
                task_id,
                db,
                account_key=account_key,
            )
            self.logger.info(
                f'[任务{task_id or "unknown"}] 覆盖同步：转存完成，'
                f'成功: {transfer_result}, 耗时: {time.time() - transfer_start_time:.2f}秒'
            )

            # 调试日志：转存后回查目标目录，验证文件是否真正到位
            try:
                await asyncio.sleep(3)  # 等网盘索引更新
                post_transfer_map = await self.list_dir(
                    service,
                    target_definition.file_path,
                    False,
                    None,
                    False,
                    target_definition,
                    target_definition.file_id,
                    task_id,
                    db,
                    account_key=account_key,
                )
                log_target_verify(
                    task_id,
                    target_definition.file_path,
                    expected_count=len(all_files_to_transfer),
                    actual_count=len(post_transfer_map),
                    actual_files=list(post_transfer_map.keys()),
                )
            except Exception as verify_err:
                log_api_call(task_id, 'transfer_verify_failed', 0, str(verify_err))

            if not transfer_result:
                self.logger.warning(f'[任务{task_id or "unknown"}] 覆盖同步转存失败: {target_definition.file_path}')
                elapsed = time.time() - start_overwrite_sync_time
                self.logger.info(
                    f'[任务{task_id or "unknown"}] 退出 _handle_overwrite_sync (转存失败), 耗时: {elapsed:.2f}秒'
                )
                return
            if db:
                await db.commit()

        except Exception as e:
            error_msg = f'覆盖同步失败: {str(e)}'
            self.logger.error(f'[任务{task_id or "unknown"}] {error_msg}', exc_info=True)
            sync_stats.add_error(stats, error_msg)

        elapsed = time.time() - start_overwrite_sync_time
        self.logger.info(f'[任务{task_id or "unknown"}] 退出 _handle_overwrite_sync, 耗时: {elapsed:.2f}秒')


# 全局实例
file_sync_service = FileSyncService()


def get_file_sync_service() -> FileSyncService:
    """获取文件同步服务实例"""
    return file_sync_service
