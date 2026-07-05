#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.coulddrive.schema.enum import RecursionSpeed
from backend.app.coulddrive.schema.file import BaseFileInfo
from backend.app.coulddrive.schema.file import CopyParam
from backend.app.coulddrive.schema.file import DiskTargetDefinition
from backend.app.coulddrive.schema.file import MkdirParam
from backend.app.coulddrive.schema.file import RemoveParam
from backend.app.coulddrive.service.coulddrive_service import CouldDriveService
from backend.app.coulddrive.service.filesync import stats as sync_stats
from backend.app.coulddrive.service.utils_service import build_full_path
from backend.app.task.tasks.filesync.debug_logger import log_api_call


class FileSyncExecutor:
    """文件同步执行器"""

    def __init__(
        self,
        *,
        logger: Any,
        check_cancel_requested: Callable[[AsyncSession, int], Awaitable[bool]],
        record_task_item: Callable[..., Awaitable[Any]],
        update_transferred_file_ids: Callable[..., Awaitable[None]],
    ) -> None:
        """
        初始化文件同步执行器

        :param logger: 日志对象
        :param check_cancel_requested: 任务取消检查回调
        :param record_task_item: 任务项记录回调
        :param update_transferred_file_ids: 转存后文件 ID 更新回调
        :return:
        """
        self._logger = logger
        self._check_cancel_requested = check_cancel_requested
        self._record_task_item = record_task_item
        self._update_transferred_file_ids = update_transferred_file_ids

    async def record_batch_task_items(
        self,
        files: list[dict[str, Any]],
        task_id: int | None,
        stats: dict[str, Any],
        status: str,
        error_msg: str | None = None,
        operation_label: str = '转存',
    ) -> None:
        """
        批量记录文件的任务项

        :param files: 文件列表
        :param task_id: 任务 ID
        :param stats: 同步统计信息字典
        :param status: 任务项状态
        :param error_msg: 错误信息
        :param operation_label: 操作名称
        :return:
        """
        if not task_id or not stats:
            return

        status_label = {'completed': f'{operation_label}成功', 'failed': f'{operation_label}失败'}.get(status, status)
        for file_info in files:
            self._logger.debug(f"[任务{task_id}] {status_label}: '{file_info.get('file_name', '')}'")
            task_item = await self._record_task_item(
                task_id,
                'copy',
                file_info.get('source_path', ''),
                file_info.get('target_path', ''),
                file_info.get('file_name', ''),
                file_info.get('file_size', 0),
                status,
                error_msg,
            )
            stats['pending_task_items'].append(task_item)

    async def copy_local_files_batch(
        self,
        service: CouldDriveService,
        target_definition: DiskTargetDefinition,
        files: list[dict[str, Any]],
        recursion_speed: RecursionSpeed,
        stats: dict[str, Any],
        task_id: int | None,
        db: AsyncSession | None = None,
        current_target_id: str | None = None,
    ) -> bool:
        """
        同盘复制文件

        :param service: 网盘服务实例
        :param target_definition: 目标定义
        :param files: 文件列表
        :param recursion_speed: 递归速度
        :param stats: 同步统计信息字典
        :param task_id: 任务 ID
        :param db: 数据库会话
        :param current_target_id: 当前目标目录 ID
        :return:
        """
        try:
            drive_type = await service.get_drive_type()
            file_paths = [
                build_full_path(file_info.get('source_path', ''), file_info.get('file_name', ''))
                for file_info in files
            ]
            file_ids = [str(file_info.get('file_id')) for file_info in files if file_info.get('file_id')]
            target_path = files[0].get('target_path') if files else target_definition.file_path
            target_id = current_target_id or target_definition.file_id
            params = CopyParam(
                drive_type=drive_type,
                file_ids=file_ids or None,
                file_paths=file_paths,
                target_id=target_id,
                target_path=target_path,
            )

            self._logger.info(f'[任务{task_id}] 执行同盘复制（已由上层获取账户锁）')
            copy_result = await service.copy(params=params)
            self._logger.info(f'[任务{task_id}] 同盘复制调用结果: {copy_result}')

            log_api_call(
                task_id,
                'copy',
                len(files),
                copy_result,
                extra={
                    'target_path': target_path,
                    'target_id': target_id,
                    'files_sample': [file_info.get('file_name', '') for file_info in files[:10]],
                },
            )

            await asyncio.sleep(2)

            if copy_result:
                stats['files_transferred'] += len(files)
                self._logger.info(f'[任务{task_id or "unknown"}] 同盘复制成功: {len(files)} 个文件')
                await self.record_batch_task_items(
                    files,
                    task_id,
                    stats,
                    'completed',
                    operation_label='复制',
                )
                await self._update_transferred_file_ids(
                    service,
                    target_definition,
                    files,
                    target_id,
                    stats,
                    task_id,
                    db,
                )
            else:
                error_msg = f'同盘复制失败：涉及 {len(files)} 个文件'
                self._logger.error(f'[任务{task_id or "unknown"}] {error_msg}')
                sync_stats.add_error(stats, error_msg)
                await self.record_batch_task_items(
                    files,
                    task_id,
                    stats,
                    'failed',
                    error_msg,
                    operation_label='复制',
                )

            if recursion_speed == RecursionSpeed.SLOW:
                await asyncio.sleep(2)
            elif recursion_speed == RecursionSpeed.NORMAL:
                await asyncio.sleep(1)

            return copy_result

        except Exception as e:
            error_msg = f'同盘复制异常: {str(e)}'
            self._logger.error(f'[任务{task_id or "unknown"}] {error_msg}', exc_info=True)
            sync_stats.add_error(stats, error_msg)
            await self.record_batch_task_items(
                files,
                task_id,
                stats,
                'failed',
                error_msg,
                operation_label='复制',
            )
            return False

    async def delete_files(
        self,
        service: CouldDriveService,
        target_definition: DiskTargetDefinition,
        files: list[dict[str, Any]],
        recursion_speed: RecursionSpeed,
        stats: dict[str, Any],
        task_id: int | None,
        db: AsyncSession | None = None,
        account_key: str | None = None,
    ) -> bool:
        """
        批量删除文件

        :param service: 网盘服务实例
        :param target_definition: 目标定义
        :param files: 文件列表
        :param recursion_speed: 递归速度
        :param stats: 同步统计信息字典
        :param task_id: 任务 ID
        :param db: 数据库会话
        :param account_key: 账户锁键
        :return:
        """
        if not files:
            self._logger.info(f'[任务{task_id or "unknown"}] 没有文件需要删除，跳过批量删除。')
            return True

        if task_id and db:
            if await self._check_cancel_requested(db, task_id):
                self._logger.info(f'[任务{task_id}] delete_files 检测到取消请求，停止删除')
                return False

        try:
            drive_type = await service.get_drive_type()
            file_paths = []
            file_ids = []
            for file_info in files:
                target_path = file_info['target_path']
                file_name = file_info['file_name']
                full_path = build_full_path(target_path, file_name)
                file_paths.append(full_path)

                if file_info.get('file_id'):
                    file_ids.append(file_info['file_id'])

            params = RemoveParam(
                drive_type=drive_type,
                file_paths=file_paths if file_paths else None,
                file_ids=file_ids if file_ids else None,
                parent_id=target_definition.file_id,
                file_name=None,
            )

            self._logger.info(f'[任务{task_id}] 执行文件删除（已由上层获取账户锁）')
            result = await service.remove(params=params)

            log_api_call(
                task_id,
                'delete',
                len(files),
                result,
                extra={'file_paths_sample': file_paths[:5], 'file_ids_sample': file_ids[:5]},
            )

            if result:
                stats['files_deleted'] += len(files)
                self._logger.info(f'[任务{task_id or "unknown"}] 批量删除成功: {len(files)} 个文件')
                await self._record_delete_task_items(files, task_id, stats, 'completed')
            else:
                error_msg = f'批量删除失败，涉及 {len(files)} 个文件'
                self._logger.error(f'[任务{task_id or "unknown"}] {error_msg}')
                sync_stats.add_error(stats, error_msg)
                await self._record_delete_task_items(files, task_id, stats, 'failed', error_msg)

            if recursion_speed == RecursionSpeed.SLOW:
                await asyncio.sleep(3)
            elif recursion_speed == RecursionSpeed.NORMAL:
                await asyncio.sleep(1)

            return result

        except Exception as e:
            error_msg = str(e)
            self._logger.error(f'[任务{task_id or "unknown"}] 批量删除文件失败: {error_msg}', exc_info=True)
            sync_stats.add_error(stats, error_msg)
            await self._record_delete_task_items(files, task_id, stats, 'failed', error_msg, exception=True)
            return False

    async def _record_delete_task_items(
        self,
        files: list[dict[str, Any]],
        task_id: int | None,
        stats: dict[str, Any],
        status: str,
        error_msg: str | None = None,
        exception: bool = False,
    ) -> None:
        """
        记录删除任务项

        :param files: 文件列表
        :param task_id: 任务 ID
        :param stats: 同步统计信息字典
        :param status: 状态
        :param error_msg: 错误信息
        :param exception: 是否异常场景
        :return:
        """
        if not task_id or not stats:
            return

        status_label = '删除成功'
        if status == 'failed':
            status_label = '删除异常' if exception else '删除失败'

        for file_info in files:
            self._logger.debug(f"[任务{task_id}] {status_label}: '{file_info['file_name']}'")
            task_item = await self._record_task_item(
                task_id,
                'delete',
                '',
                file_info['target_path'],
                file_info['file_name'],
                file_info['file_size'],
                status,
                error_msg,
            )
            stats['pending_task_items'].append(task_item)

    async def create_directory(
        self,
        service: CouldDriveService,
        target_definition: DiskTargetDefinition,
        dir_name: str,
        task_id: int | None,
        parent_id: str | None = None,
    ) -> BaseFileInfo | None:
        """
        创建目录

        :param service: 网盘服务实例
        :param target_definition: 目标定义
        :param dir_name: 目录名
        :param task_id: 任务 ID
        :param parent_id: 父目录 ID
        :return:
        """
        try:
            drive_type = await service.get_drive_type()
            actual_parent_id = parent_id or target_definition.file_id
            params = MkdirParam(
                drive_type=drive_type,
                file_path=target_definition.file_path,
                file_name=dir_name,
                parent_id=actual_parent_id,
                return_if_exist=True,
            )

            result = await service.mkdir(params=params)
            if result is not None and result.file_id is not None:
                self._logger.info(f'[任务{task_id or "unknown"}] 成功创建目录: {dir_name}, file_id: {result.file_id}')
                return result

            self._logger.error(f'[任务{task_id or "unknown"}] 创建目录失败: {dir_name}, API返回结果: {result}')
            return None

        except Exception as e:
            self._logger.error(f'[任务{task_id or "unknown"}] 创建目录异常: {dir_name}, 错误: {e}')
            return None
