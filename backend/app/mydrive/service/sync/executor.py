#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.mydrive.crud.crud_space import mydrive_space_dao
from backend.app.mydrive.crud.crud_sync import (
    mydrive_sync_config_dao,
    mydrive_sync_rule_dao,
    mydrive_sync_task_dao,
    mydrive_sync_task_item_dao,
)
from backend.app.mydrive.model.space import MyDriveSpace
from backend.app.mydrive.model.sync import MyDriveSyncTaskItem
from backend.app.mydrive.service.drives.baidu.client import BaiduRequestError
from backend.app.mydrive.service.drives.quark.client import QuarkRequestError
from backend.app.mydrive.service.drives.thunder.client import ThunderRequestError
from backend.app.mydrive.service.filesystem.exceptions import MyDriveError
from backend.app.mydrive.service.filesystem.factory import create_file_space
from backend.app.mydrive.service.filesystem.models import FileObject, SpaceType
from backend.app.mydrive.service.filesystem.spaces import FileSpace, ShareableFileSpace, TransferSource, WritableFileSpace
from backend.app.mydrive.service.space_service import mydrive_space_service
from backend.app.mydrive.service.sync.account_lock import (
    MyDriveSyncAccountLockError,
    acquire_sync_account_lock,
)
from backend.app.mydrive.service.sync.planner import build_directory_sync_plan, build_post_copy_rename_plan
from backend.app.mydrive.service.sync.policy import validate_sync_spaces
from backend.app.mydrive.service.sync.rules import SyncRule, should_exclude
from backend.app.mydrive.service.transfer_service import transfer_files
from backend.common.exception import errors
from backend.common.log import log
from backend.utils.timezone import timezone


class MyDriveSyncExecutor:
    """文件同步任务执行器"""

    async def execute(self, db: AsyncSession, task_id: int) -> dict[str, Any]:
        """
        执行同步任务。

        :param db: 数据库会话
        :param task_id: 同步任务 ID
        :return:
        """
        task = await mydrive_sync_task_dao.select_model(db, task_id)
        if task is None or task.deleted:
            raise errors.NotFoundError(msg='同步任务不存在')
        if task.status != 'pending':
            raise errors.ForbiddenError(msg='同步任务不是待执行状态')

        config = await mydrive_sync_config_dao.select_model(db, task.config_id)
        if config is None or config.deleted or not config.is_enabled:
            await self._finish_task(db, task_id, 'failed', '同步配置不存在或已停用')
            return {'success': False, 'task_id': task_id, 'error': '同步配置不存在或已停用'}

        source_space = await mydrive_space_dao.get(db, config.source_space_id, config.owner_id)
        target_space = await mydrive_space_dao.get(db, config.target_space_id, config.owner_id)
        if source_space is None or target_space is None:
            await self._finish_task(db, task_id, 'failed', '同步来源或目标文件空间不存在')
            return {'success': False, 'task_id': task_id, 'error': '同步来源或目标文件空间不存在'}

        try:
            validate_sync_spaces(source_space, target_space)
            rules = await self._get_rules(db, config.rule_set_id)
            account_keys = self._get_account_lock_keys(source_space, target_space)
            async with acquire_sync_account_lock(account_keys) as account_lock:
                if await self._is_cancel_requested(db, task_id):
                    await self._finish_task(db, task_id, 'cancelled', None)
                    return {'success': False, 'task_id': task_id, 'cancelled': True}
                await mydrive_sync_task_dao.update_model(
                    db,
                    task_id,
                    {'status': 'running', 'started_at': timezone.now(), 'error_message': None},
                )
                source = await self._create_source_space(db, source_space, target_space)
                target = await create_file_space(db, target_space)
                try:
                    if not isinstance(target, WritableFileSpace):
                        raise errors.ForbiddenError(msg='同步目标不支持写入')
                    source_directory = await self._resolve_directory(source, config.source_path)
                    target_directory = await self._ensure_directory(target, config.target_path)
                    if config.sync_method == 'overwrite':
                        await self._overwrite_directory(
                            db,
                            task_id,
                            source,
                            target,
                            target_space,
                            source_directory,
                            target_directory,
                            config.source_path,
                            config.target_path,
                            rules,
                        )
                    else:
                        await self._sync_directory(
                            db,
                            task_id,
                            source,
                            target,
                            target_space,
                            source_directory,
                            target_directory,
                            config.source_path,
                            config.target_path,
                            config.sync_method,
                            rules,
                            config.source_path,
                            config.target_path,
                        )
                    if account_lock.lease_lost:
                        raise errors.ForbiddenError(msg='网盘账户同步锁租约已丢失，已停止任务')
                finally:
                    await source.aclose()
                    await target.aclose()
                    await mydrive_space_service.invalidate_space_cache(target_space.id)
        except MyDriveSyncAccountLockError as exc:
            await self._finish_task(db, task_id, 'failed', str(exc))
            return {'success': False, 'task_id': task_id, 'error': str(exc)}
        except errors.ForbiddenError as exc:
            await self._finish_task(db, task_id, 'failed', exc.msg)
            return {'success': False, 'task_id': task_id, 'error': exc.msg}
        except (MyDriveError, BaiduRequestError, QuarkRequestError, ThunderRequestError) as exc:
            error_message = str(exc)
            await self._finish_task(db, task_id, 'failed', error_message)
            return {'success': False, 'task_id': task_id, 'error': error_message}
        except Exception as exc:
            log.exception('MyDrive 同步任务 {} 执行失败: {}', task_id, exc)
            await self._finish_task(db, task_id, 'failed', str(exc))
            return {'success': False, 'task_id': task_id, 'error': str(exc)}

        task = await mydrive_sync_task_dao.select_model(db, task_id)
        if task is not None and task.cancel_requested:
            await self._finish_task(db, task_id, 'cancelled', None)
            return {'success': False, 'task_id': task_id, 'cancelled': True}
        await mydrive_sync_config_dao.update_model(db, config.id, {'last_synced_at': timezone.now()})
        await self._finish_task(db, task_id, 'completed', None)
        return {'success': True, 'task_id': task_id}

    @staticmethod
    def _get_account_lock_keys(source_space: MyDriveSpace, target_space: MyDriveSpace) -> set[str]:
        """获取同步涉及的网盘账户锁标识。"""
        account_keys = {f'{target_space.provider}:{target_space.account_id}'}
        if source_space.account_id is not None:
            account_keys.add(f'{source_space.provider}:{source_space.account_id}')
        return account_keys

    async def _sync_directory(
        self,
        db: AsyncSession,
        task_id: int,
        source: FileSpace,
        target: WritableFileSpace,
        target_space_record: MyDriveSpace,
        source_directory: FileObject | None,
        target_directory: FileObject | None,
        source_path: str,
        target_path: str,
        sync_method: str,
        rules: list[SyncRule],
        source_root_path: str,
        target_root_path: str,
    ) -> None:
        """递归同步单个目录。"""
        if await self._is_cancel_requested(db, task_id):
            return

        source_items = await source.list(source_directory)
        filtered_source_items = [
            item
            for item in source_items
            if not should_exclude(
                self._relative_path(item.path, source_root_path),
                item.is_directory,
                rules,
            )
        ]
        target_items = await target.list(target_directory)
        plan = build_directory_sync_plan(filtered_source_items, target_items, sync_method, rules)
        target_by_name = {item.name: item for item in target_items}
        removed_target_ids: set[str] = set()

        for source_item in filtered_source_items:
            target_item = target_by_name.get(source_item.name)
            if target_item is None or target_item.is_directory == source_item.is_directory:
                continue
            await self._remove_item(db, task_id, target, target_item, target_path)
            removed_target_ids.add(target_item.file_id)

        for directory in plan.directories_to_create:
            existing = target_by_name.get(directory.name)
            if existing is not None and not existing.is_directory:
                await self._remove_item(db, task_id, target, existing, target_path)
            created_directory = await target.make_directory(directory.name, target_directory)
            await self._record_item(
                db,
                task_id,
                'create_directory',
                directory.path,
                created_directory.path,
                directory.name,
                0,
                'completed',
            )
            await self._sync_directory(
                db,
                task_id,
                source,
                target,
                target_space_record,
                directory,
                created_directory,
                directory.path,
                created_directory.path,
                sync_method,
                rules,
                source_root_path,
                target_root_path,
            )

        for source_directory_item in filtered_source_items:
            if not source_directory_item.is_directory or source_directory_item in plan.directories_to_create:
                continue
            target_directory_item = target_by_name.get(source_directory_item.name)
            if target_directory_item is None or not target_directory_item.is_directory:
                continue
            await self._sync_directory(
                db,
                task_id,
                source,
                target,
                target_space_record,
                source_directory_item,
                target_directory_item,
                source_directory_item.path,
                target_directory_item.path,
                sync_method,
                rules,
                source_root_path,
                target_root_path,
            )

        copied_files = await self._copy_files(
            db,
            task_id,
            source,
            target,
            target_space_record,
            plan.files_to_copy,
            target_directory,
            source_path,
            target_path,
        )
        for source_file, renamed_name in build_post_copy_rename_plan(copied_files, rules):
            renamed_file = await target.rename(source_file, renamed_name)
            await self._record_item(
                db,
                task_id,
                'rename',
                source_file.path,
                renamed_file.path,
                source_file.name,
                source_file.size or 0,
                'completed',
            )

        target_items_to_remove = [
            target_item
            for target_item in plan.target_items_to_remove
            if target_item.file_id not in removed_target_ids
            and (sync_method == 'full' or target_item.name in {item.name for item in filtered_source_items})
            and not should_exclude(
                self._relative_path(target_item.path, target_root_path),
                target_item.is_directory,
                rules,
            )
        ]
        await self._remove_items(db, task_id, target, target_items_to_remove, target_path)

    async def _overwrite_directory(
        self,
        db: AsyncSession,
        task_id: int,
        source: FileSpace,
        target: WritableFileSpace,
        target_space_record: MyDriveSpace,
        source_directory: FileObject | None,
        target_directory: FileObject | None,
        source_path: str,
        target_path: str,
        rules: list[SyncRule],
    ) -> None:
        """覆盖同步当前目录，不递归处理子目录。"""
        source_items = await source.list(source_directory)
        if not source_items:
            raise errors.ForbiddenError(msg='源目录为空，已跳过覆盖同步以保护目标数据')

        excluded_names = {
            item.name
            for item in source_items
            if should_exclude(self._relative_path(item.path, source_path), item.is_directory, rules)
        }
        transfer_items = [item for item in source_items if item.name not in excluded_names]
        target_items = await target.list(target_directory)
        removable_items = [item for item in target_items if item.name not in excluded_names]
        await self._remove_items(db, task_id, target, removable_items, target_path)

        copied_files = await self._copy_files(
            db,
            task_id,
            source,
            target,
            target_space_record,
            transfer_items,
            target_directory,
            source_path,
            target_path,
        )
        for source_file, renamed_name in build_post_copy_rename_plan(copied_files, rules):
            renamed_file = await target.rename(source_file, renamed_name)
            await self._record_item(
                db,
                task_id,
                'rename',
                source_file.path,
                renamed_file.path,
                source_file.name,
                source_file.size or 0,
                'completed',
            )

    async def _copy_files(
        self,
        db: AsyncSession,
        task_id: int,
        source: FileSpace,
        target: WritableFileSpace,
        target_space_record: MyDriveSpace,
        files: list[FileObject],
        target_directory: FileObject | None,
        source_path: str,
        target_path: str,
    ) -> list[FileObject]:
        """复制或转存当前目录文件。"""
        if not files or await self._is_cancel_requested(db, task_id):
            return []
        if isinstance(source, TransferSource):
            copied_files = await transfer_files(source, files, target, target_directory)
            operation = 'transfer'
        elif isinstance(source, WritableFileSpace):
            if source.locator.account_id != target.locator.account_id:
                copied_files = await self._transfer_cross_account_files(
                    db,
                    task_id,
                    source,
                    target,
                    target_space_record,
                    files,
                    target_directory,
                )
                operation = 'transfer'
            else:
                await source.copy(files, target_directory)
                copied_files = await self._resolve_copied_files(target, files, target_directory)
                operation = 'copy'
        else:
            raise errors.ForbiddenError(msg='当前同步来源不支持复制或转存')

        for file in files:
            await self._record_item(
                db,
                task_id,
                operation,
                file.path,
                str(PurePosixPath(target_path) / file.name),
                file.name,
                file.size or 0,
                'completed',
            )
        return copied_files

    async def _transfer_cross_account_files(
        self,
        db: AsyncSession,
        task_id: int,
        source: WritableFileSpace,
        target: WritableFileSpace,
        target_space_record: MyDriveSpace,
        files: list[FileObject],
        target_directory: FileObject | None,
    ) -> list[FileObject]:
        """通过临时分享执行同 Provider 跨账户转存。"""
        if not isinstance(source, ShareableFileSpace):
            raise errors.ForbiddenError(msg='当前来源不支持跨账户同步')
        share = await source.create_share(files, f'MyDrive Sync {task_id}', 1)
        temporary_space = MyDriveSpace(
            owner_id=target_space_record.owner_id,
            provider=share.provider,
            space_type=SpaceType.SHARE_LINK.value,
            name=f'MyDrive Sync {task_id}',
            source_key=share.url if share.provider == 'baidu' else share.share_id,
            account_id=target_space_record.account_id,
            source_ref=self._get_temporary_share_ref(share.provider, share.share_id, share.url, share.password),
        )
        temporary_source = await create_file_space(db, temporary_space)
        try:
            source_items = await temporary_source.list()
            source_by_name = {item.name: item for item in source_items}
            transfer_items = [source_by_name[file.name] for file in files if file.name in source_by_name]
            if len(transfer_items) != len(files):
                raise errors.ForbiddenError(msg='临时分享文件未完整加载，已停止跨账户同步')
            if not isinstance(temporary_source, TransferSource):
                raise errors.ForbiddenError(msg='临时分享空间不支持转存')
            return await transfer_files(temporary_source, transfer_items, target, target_directory)
        finally:
            await temporary_source.aclose()
            try:
                await source.cancel_shares([share.share_id])
            except Exception as exc:
                log.warning('MyDrive 同步临时分享 {} 取消失败: {}', share.share_id, exc)

    @staticmethod
    def _get_temporary_share_ref(provider: str, share_id: str, url: str, password: str) -> dict[str, str]:
        """构建临时分享空间来源信息。"""
        if provider == 'baidu':
            return {'url': url, 'passcode': password}
        if provider == 'quark':
            return {'share_id': share_id, 'passcode': password}
        raise errors.ForbiddenError(msg=f'暂不支持 {provider} 跨账户同步')

    async def _create_source_space(
        self,
        db: AsyncSession,
        source_space: MyDriveSpace,
        target_space: MyDriveSpace,
    ) -> FileSpace:
        """创建同步来源文件空间。"""
        if source_space.space_type != SpaceType.SHARE_LINK.value or source_space.account_id == target_space.account_id:
            return await create_file_space(db, source_space)
        temporary_source = MyDriveSpace(
            owner_id=source_space.owner_id,
            provider=source_space.provider,
            space_type=source_space.space_type,
            name=source_space.name,
            source_key=source_space.source_key,
            account_id=target_space.account_id,
            root_id=source_space.root_id,
            root_path=source_space.root_path,
            source_ref=source_space.source_ref,
            capabilities=source_space.capabilities,
            is_enabled=source_space.is_enabled,
        )
        return await create_file_space(db, temporary_source)

    async def _get_rules(self, db: AsyncSession, rule_set_id: int | None) -> list[SyncRule]:
        """获取已启用的同步规则。"""
        if rule_set_id is None:
            return []
        rules = await mydrive_sync_rule_dao.list_by_rule_set(db, rule_set_id)
        return [
            SyncRule(
                rule_type=rule.rule_type,
                pattern=rule.pattern,
                replacement=rule.replacement,
                is_enabled=rule.is_enabled,
            )
            for rule in rules
        ]

    async def _resolve_directory(self, file_space: FileSpace, path: str) -> FileObject | None:
        """解析挂载内目录。"""
        normalized_path = str(PurePosixPath(path))
        if normalized_path in {'.', '/'}:
            return None
        current_directory: FileObject | None = None
        for directory_name in normalized_path.strip('/').split('/'):
            current_directory = next(
                (item for item in await file_space.list(current_directory) if item.is_directory and item.name == directory_name),
                None,
            )
            if current_directory is None:
                raise errors.NotFoundError(msg=f'同步目录不存在: {path}')
        return current_directory

    async def _ensure_directory(self, file_space: WritableFileSpace, path: str) -> FileObject | None:
        """解析或逐级创建挂载内目录。"""
        normalized_path = str(PurePosixPath(path))
        if normalized_path in {'.', '/'}:
            return None
        current_directory: FileObject | None = None
        for directory_name in normalized_path.strip('/').split('/'):
            current_directory = next(
                (
                    item
                    for item in await file_space.list(current_directory)
                    if item.is_directory and item.name == directory_name
                ),
                None,
            ) or await file_space.make_directory(directory_name, current_directory)
        return current_directory

    async def _resolve_copied_files(
        self,
        target: WritableFileSpace,
        source_files: list[FileObject],
        target_directory: FileObject | None,
    ) -> list[FileObject]:
        """重新读取已复制文件。"""
        copied_names = {file.name for file in source_files}
        return [file for file in await target.list(target_directory) if file.name in copied_names]

    async def _remove_item(
        self,
        db: AsyncSession,
        task_id: int,
        target: WritableFileSpace,
        target_item: FileObject,
        target_path: str,
    ) -> None:
        """删除目标文件并记录明细。"""
        await self._remove_items(db, task_id, target, [target_item], target_path)

    async def _remove_items(
        self,
        db: AsyncSession,
        task_id: int,
        target: WritableFileSpace,
        target_items: list[FileObject],
        target_path: str,
    ) -> None:
        """
        批量删除目标文件并记录明细。

        :param db: 数据库会话
        :param task_id: 同步任务 ID
        :param target: 目标文件空间
        :param target_items: 待删除文件
        :param target_path: 目标目录路径
        :return:
        """
        if not target_items or await self._is_cancel_requested(db, task_id):
            return
        await target.remove(target_items)
        for target_item in target_items:
            await self._record_item(
                db,
                task_id,
                'remove',
                '',
                target_path,
                target_item.name,
                target_item.size or 0,
                'completed',
            )

    async def _is_cancel_requested(self, db: AsyncSession, task_id: int) -> bool:
        """判断同步任务是否已请求取消。"""
        task = await mydrive_sync_task_dao.select_model(db, task_id)
        return task is None or task.cancel_requested

    async def _record_item(
        self,
        db: AsyncSession,
        task_id: int,
        operation: str,
        source_path: str,
        target_path: str,
        file_name: str,
        file_size: int,
        status: str,
        error_message: str | None = None,
    ) -> None:
        """记录同步任务执行明细。"""
        db.add(
            MyDriveSyncTaskItem(
                task_id=task_id,
                operation=operation,
                source_path=source_path,
                target_path=target_path,
                file_name=file_name,
                file_size=file_size,
                status=status,
                error_message=error_message,
            )
        )
        task = await mydrive_sync_task_dao.select_model(db, task_id)
        if task is None:
            return
        statistics = dict(task.statistics)
        statistics['planned'] = statistics.get('planned', 0) + 1
        statistics[status] = statistics.get(status, 0) + 1
        await mydrive_sync_task_dao.update_model(db, task_id, {'statistics': statistics})

    @staticmethod
    def _relative_path(path: str, root_path: str) -> str:
        """获取文件相对于同步根目录的路径。"""
        normalized_path = PurePosixPath(path)
        normalized_root = PurePosixPath(root_path)
        try:
            return str(normalized_path.relative_to(normalized_root))
        except ValueError:
            return normalized_path.name

    async def _finish_task(
        self,
        db: AsyncSession,
        task_id: int,
        status: str,
        error_message: str | None,
    ) -> None:
        """完成同步任务并持久化状态。"""
        await mydrive_sync_task_dao.update_model(
            db,
            task_id,
            {'status': status, 'error_message': error_message, 'finished_at': timezone.now()},
        )


mydrive_sync_executor: MyDriveSyncExecutor = MyDriveSyncExecutor()
