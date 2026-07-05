#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from collections import defaultdict
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.coulddrive.schema.file import DiskTargetDefinition
from backend.app.coulddrive.schema.file import RenameParam
from backend.app.coulddrive.schema.file import ShareSourceDefinition
from backend.app.coulddrive.service.coulddrive_service import CouldDriveService
from backend.app.coulddrive.service.filesync import stats as sync_stats
from backend.app.coulddrive.service.rule_template_service import ItemFilter
from backend.app.coulddrive.service.utils_service import build_full_path
from backend.app.coulddrive.service.utils_service import join_path


class LocalSyncGuard:
    """本地同步保护策略"""

    COPY_COUNT_LIMIT = 500
    COPY_RATIO_LIMIT = 0.3
    DELETE_COUNT_LIMIT = 100
    DELETE_RATIO_LIMIT = 0.1
    RATIO_MIN_BASE = 20
    RENAME_CANDIDATE_LIMIT = 20
    FINGERPRINT_ITEM_LIMIT = 5000

    def __init__(
        self,
        *,
        logger: Any,
        list_dir: Callable[..., Awaitable[dict[str, dict[str, Any]]]],
        record_task_item: Callable[..., Awaitable[Any]],
    ) -> None:
        """
        初始化本地同步保护策略

        :param logger: 日志对象
        :param list_dir: 目录列表回调
        :param record_task_item: 任务项记录回调
        :return:
        """
        self._logger = logger
        self._list_dir = list_dir
        self._record_task_item = record_task_item

    @staticmethod
    def is_local_source(source_definition: ShareSourceDefinition) -> bool:
        """
        判断同步源是否为本地网盘路径

        :param source_definition: 源定义
        :return:
        """
        return source_definition.source_type == 'local'

    def add_warning(self, stats: dict[str, Any], message: str) -> None:
        """
        添加同步警告

        :param stats: 同步统计信息字典
        :param message: 警告内容
        :return:
        """
        sync_stats.add_warning(stats=stats, logger=self._logger, message=message)

    def mark_protection_skip(self, stats: dict[str, Any], task_id: int | None, message: str) -> None:
        """
        标记本地同步保护性跳过

        :param stats: 同步统计信息字典
        :param task_id: 任务 ID
        :param message: 跳过原因
        :return:
        """
        sync_stats.mark_protection_skip(stats=stats, logger=self._logger, task_id=task_id, message=message)

    @staticmethod
    def _split_file_map_names(file_map: dict[str, Any]) -> tuple[list[str], list[str]]:
        """
        拆分目录名和文件名

        :param file_map: 文件映射
        :return:
        """
        dir_names = [name for name in file_map if name.endswith('/')]
        file_names = [name for name in file_map if not name.endswith('/')]
        return dir_names, file_names

    async def _build_directory_fingerprint(
        self,
        service: CouldDriveService,
        path: str,
        is_src: bool,
        definition: ShareSourceDefinition | DiskTargetDefinition,
        item_filter: ItemFilter | None,
        task_id: int | None,
        db: AsyncSession | None,
        target_id: str | None = None,
        account_key: str | None = None,
    ) -> dict[str, Any] | None:
        """
        生成目录内容指纹

        :param service: 网盘服务实例
        :param path: 目录路径
        :param is_src: 是否源目录
        :param definition: 目录定义
        :param item_filter: 过滤器
        :param task_id: 任务 ID
        :param db: 数据库会话
        :param target_id: 目标目录 ID
        :param account_key: 账户锁键
        :return:
        """
        entries: list[str] = []
        file_count = 0
        dir_count = 0
        total_size = 0

        async def walk(current_path: str, current_target_id: str | None, relative_prefix: str) -> bool:
            nonlocal file_count, dir_count, total_size

            if len(entries) > self.FINGERPRINT_ITEM_LIMIT:
                return False

            file_map = await self._list_dir(
                service,
                current_path,
                False,
                item_filter,
                is_src,
                definition,
                current_target_id,
                task_id,
                db,
                account_key=account_key,
            )

            for item_name, item_info in sorted(file_map.items()):
                clean_name = item_name.rstrip('/')
                relative_path = f'{relative_prefix}{clean_name}'
                if item_name.endswith('/'):
                    dir_count += 1
                    entries.append(f'D:{relative_path}/')
                    child_path = join_path(current_path, clean_name, is_dir=True)
                    child_target_id = item_info.get('file_id') if not is_src else None
                    if not await walk(child_path, child_target_id, f'{relative_path}/'):
                        return False
                    continue

                file_size = int(item_info.get('file_size', 0) or 0)
                file_count += 1
                total_size += file_size
                entries.append(f'F:{relative_path}:{file_size}')
                if len(entries) > self.FINGERPRINT_ITEM_LIMIT:
                    return False

            return True

        try:
            if not await walk(path, target_id, ''):
                return None
        except Exception as e:
            self._logger.warning(f'[任务{task_id or "unknown"}] 生成目录指纹失败: {path}, 错误: {e}')
            return None

        return {
            'key': (file_count, dir_count, total_size, tuple(entries)),
            'file_count': file_count,
            'dir_count': dir_count,
            'total_size': total_size,
            'item_count': file_count + dir_count,
        }

    async def _estimate_missing_source_changes(
        self,
        service: CouldDriveService,
        source_definition: ShareSourceDefinition,
        source_path: str,
        source_file_map: dict[str, Any],
        missing_names: list[str],
        item_filter: ItemFilter | None,
        stats: dict[str, Any],
        task_id: int | None,
        db: AsyncSession | None,
        account_key: str | None = None,
    ) -> dict[str, int] | None:
        """
        估算本地源新增内容规模

        :param service: 网盘服务实例
        :param source_definition: 源定义
        :param source_path: 源目录路径
        :param source_file_map: 源文件映射
        :param missing_names: 目标缺失的源名称
        :param item_filter: 过滤器
        :param stats: 同步统计信息字典
        :param task_id: 任务 ID
        :param db: 数据库会话
        :param account_key: 账户锁键
        :return:
        """
        missing_dir_names = [name for name in missing_names if name.endswith('/')]
        if len(missing_dir_names) > self.RENAME_CANDIDATE_LIMIT:
            return None

        total_count = 0
        total_size = 0
        for missing_name in missing_names:
            item_info = source_file_map[missing_name]
            if not missing_name.endswith('/'):
                total_count += 1
                total_size += int(item_info.get('file_size', 0) or 0)
                continue

            dir_name = missing_name.rstrip('/')
            dir_path = join_path(source_path, dir_name, is_dir=True)
            fingerprint = await self._build_directory_fingerprint(
                service,
                dir_path,
                True,
                source_definition,
                item_filter,
                task_id,
                db,
                account_key=account_key,
            )
            if fingerprint is None:
                return None
            total_count += 1 + fingerprint['item_count']
            total_size += fingerprint['total_size']

        stats['local_planned_copy_count'] = stats.get('local_planned_copy_count', 0) + total_count
        stats['local_planned_copy_size'] = stats.get('local_planned_copy_size', 0) + total_size
        return {'count': total_count, 'size': total_size}

    async def _estimate_target_delete_changes(
        self,
        service: CouldDriveService,
        target_definition: DiskTargetDefinition,
        target_path: str,
        target_id: str | None,
        target_file_map: dict[str, Any],
        extra_names: list[str],
        item_filter: ItemFilter | None,
        stats: dict[str, Any],
        task_id: int | None,
        db: AsyncSession | None,
        account_key: str | None = None,
    ) -> dict[str, int] | None:
        """
        估算本地目标删除内容规模

        :param service: 网盘服务实例
        :param target_definition: 目标定义
        :param target_path: 目标路径
        :param target_id: 目标目录 ID
        :param target_file_map: 目标文件映射
        :param extra_names: 源中不存在的目标名称
        :param item_filter: 过滤器
        :param stats: 同步统计信息字典
        :param task_id: 任务 ID
        :param db: 数据库会话
        :param account_key: 账户锁键
        :return:
        """
        extra_dir_names = [name for name in extra_names if name.endswith('/')]
        if len(extra_dir_names) > self.RENAME_CANDIDATE_LIMIT:
            return None

        total_count = 0
        total_size = 0
        for extra_name in extra_names:
            item_info = target_file_map[extra_name]
            if not extra_name.endswith('/'):
                total_count += 1
                total_size += int(item_info.get('file_size', 0) or 0)
                continue

            dir_name = extra_name.rstrip('/')
            dir_path = join_path(target_path, dir_name, is_dir=True)
            fingerprint = await self._build_directory_fingerprint(
                service,
                dir_path,
                False,
                target_definition,
                item_filter,
                task_id,
                db,
                item_info.get('file_id') or target_id,
                account_key=account_key,
            )
            if fingerprint is None:
                return None
            total_count += 1 + fingerprint['item_count']
            total_size += fingerprint['total_size']

        stats['local_planned_delete_count'] = stats.get('local_planned_delete_count', 0) + total_count
        stats['local_planned_delete_size'] = stats.get('local_planned_delete_size', 0) + total_size
        return {'count': total_count, 'size': total_size}

    async def _rename_target_dir(
        self,
        service: CouldDriveService,
        target_path: str,
        target_id: str | None,
        old_dir_name: str,
        new_dir_name: str,
        target_file_info: dict[str, Any],
        stats: dict[str, Any],
        task_id: int | None,
    ) -> bool:
        """
        执行本地目标目录重命名

        :param service: 网盘服务实例
        :param target_path: 目标父路径
        :param target_id: 目标父目录 ID
        :param old_dir_name: 旧目录名
        :param new_dir_name: 新目录名
        :param target_file_info: 旧目录信息
        :param stats: 同步统计信息字典
        :param task_id: 任务 ID
        :return:
        """
        drive_type = await service.get_drive_type()
        old_path = build_full_path(target_path, old_dir_name)
        new_path = build_full_path(target_path, new_dir_name)
        params = RenameParam(
            drive_type=drive_type,
            file_id=target_file_info.get('file_id') or None,
            file_path=old_path,
            file_name=old_dir_name,
            parent_id=target_id,
            new_path=new_path,
            new_name=new_dir_name,
        )
        rename_result = await service.rename(params=params)
        if not rename_result:
            return False

        stats['folders_renamed'] = stats.get('folders_renamed', 0) + 1
        if task_id:
            task_item = await self._record_task_item(
                task_id,
                'rename',
                old_path,
                new_path,
                old_dir_name,
                0,
                'completed',
                None,
            )
            stats['pending_task_items'].append(task_item)
        self._logger.info(f'[任务{task_id or "unknown"}] 目录改名识别成功: {old_path} -> {new_path}')
        return True

    async def apply_same_parent_dir_renames(
        self,
        service: CouldDriveService,
        source_definition: ShareSourceDefinition,
        target_definition: DiskTargetDefinition,
        source_path: str,
        target_path: str,
        target_id: str | None,
        source_file_map: dict[str, Any],
        target_file_map: dict[str, Any],
        item_filter: ItemFilter | None,
        stats: dict[str, Any],
        task_id: int | None,
        db: AsyncSession | None,
        account_key: str | None = None,
    ) -> bool:
        """
        识别并处理同父目录下的确定性目录改名

        :param service: 网盘服务实例
        :param source_definition: 源定义
        :param target_definition: 目标定义
        :param source_path: 源父路径
        :param target_path: 目标父路径
        :param target_id: 目标父目录 ID
        :param source_file_map: 源文件映射
        :param target_file_map: 目标文件映射
        :param item_filter: 过滤器
        :param stats: 同步统计信息字典
        :param task_id: 任务 ID
        :param db: 数据库会话
        :param account_key: 账户锁键
        :return:
        """
        if not self.is_local_source(source_definition):
            return True

        source_dirs, _ = self._split_file_map_names(source_file_map)
        target_dirs, _ = self._split_file_map_names(target_file_map)
        source_missing_dirs = [name for name in source_dirs if name not in target_file_map]
        target_extra_dirs = [name for name in target_dirs if name not in source_file_map]
        if not source_missing_dirs or not target_extra_dirs:
            return True

        if (
            len(source_missing_dirs) > self.RENAME_CANDIDATE_LIMIT
            or len(target_extra_dirs) > self.RENAME_CANDIDATE_LIMIT
        ):
            return True

        source_fingerprints: dict[tuple[Any, ...], list[str]] = defaultdict(list)
        target_fingerprints: dict[tuple[Any, ...], list[str]] = defaultdict(list)

        for source_dir in source_missing_dirs:
            dir_name = source_dir.rstrip('/')
            fingerprint = await self._build_directory_fingerprint(
                service,
                join_path(source_path, dir_name, is_dir=True),
                True,
                source_definition,
                item_filter,
                task_id,
                db,
                account_key=account_key,
            )
            if fingerprint:
                source_fingerprints[fingerprint['key']].append(source_dir)

        for target_dir in target_extra_dirs:
            dir_name = target_dir.rstrip('/')
            target_file_info = target_file_map[target_dir]
            fingerprint = await self._build_directory_fingerprint(
                service,
                join_path(target_path, dir_name, is_dir=True),
                False,
                target_definition,
                item_filter,
                task_id,
                db,
                target_file_info.get('file_id') or target_id,
                account_key=account_key,
            )
            if fingerprint:
                target_fingerprints[fingerprint['key']].append(target_dir)

        used_target_dirs: set[str] = set()
        for fingerprint_key, matched_source_dirs in source_fingerprints.items():
            matched_target_dirs = target_fingerprints.get(fingerprint_key, [])
            if len(matched_source_dirs) != 1 or len(matched_target_dirs) != 1:
                continue

            source_dir = matched_source_dirs[0]
            target_dir = matched_target_dirs[0]
            if target_dir in used_target_dirs:
                continue

            old_dir_name = target_dir.rstrip('/')
            new_dir_name = source_dir.rstrip('/')
            target_file_info = target_file_map[target_dir]
            renamed = await self._rename_target_dir(
                service,
                target_path,
                target_id,
                old_dir_name,
                new_dir_name,
                target_file_info,
                stats,
                task_id,
            )
            if not renamed:
                self.mark_protection_skip(
                    stats,
                    task_id,
                    f'检测到目录改名但执行重命名失败，已停止同步: {old_dir_name} -> {new_dir_name}',
                )
                return False

            used_target_dirs.add(target_dir)
            target_file_map[source_dir] = target_file_map.pop(target_dir)

        return True

    async def guard_directory_changes(
        self,
        service: CouldDriveService,
        source_definition: ShareSourceDefinition,
        target_definition: DiskTargetDefinition,
        source_path: str,
        target_path: str,
        target_id: str | None,
        source_file_map: dict[str, Any],
        target_file_map: dict[str, Any],
        sync_method: str,
        item_filter: ItemFilter | None,
        stats: dict[str, Any],
        task_id: int | None,
        db: AsyncSession | None,
        account_key: str | None = None,
    ) -> bool:
        """
        对本地同步做大变更保护

        :param service: 网盘服务实例
        :param source_definition: 源定义
        :param target_definition: 目标定义
        :param source_path: 源路径
        :param target_path: 目标路径
        :param target_id: 目标目录 ID
        :param source_file_map: 源文件映射
        :param target_file_map: 目标文件映射
        :param sync_method: 同步方式
        :param item_filter: 过滤器
        :param stats: 同步统计信息字典
        :param task_id: 任务 ID
        :param db: 数据库会话
        :param account_key: 账户锁键
        :return:
        """
        if not self.is_local_source(source_definition):
            return True

        if not source_file_map and target_file_map:
            self.mark_protection_skip(
                stats,
                task_id,
                f'本地源目录为空但目标非空，疑似源异常，已跳过: {source_path} -> {target_path}',
            )
            return False

        source_missing = [name for name in source_file_map if name not in target_file_map]
        target_extra = [name for name in target_file_map if name not in source_file_map]
        if not source_missing and not target_extra:
            return True

        if source_missing and target_extra:
            if sync_method != 'full' and self._is_safe_incremental_file_addition(source_missing, target_extra):
                self.add_warning(
                    stats,
                    (
                        f'[任务{task_id or "unknown"}] 本地增量同步检测到新增文件和目标多余目录同时存在，'
                        f'已继续复制新增文件并保留目标目录: 源新增={source_missing[:5]}, 目标多余={target_extra[:5]}'
                    ),
                )
                return True

            self.mark_protection_skip(
                stats,
                task_id,
                (
                    '本地同步检测到新增和目标多余内容同时存在，疑似目录改名或结构整理，已跳过: '
                    f'源新增={source_missing[:5]}, 目标多余={target_extra[:5]}'
                ),
            )
            return False

        target_base_count = max(len(target_file_map), 1)
        if source_missing:
            copy_estimate = await self._estimate_missing_source_changes(
                service,
                source_definition,
                source_path,
                source_file_map,
                source_missing,
                item_filter,
                stats,
                task_id,
                db,
                account_key=account_key,
            )
            if copy_estimate is None:
                self.mark_protection_skip(
                    stats,
                    task_id,
                    f'本地新增内容过多或无法估算，已跳过: {source_path} -> {target_path}',
                )
                return False

            copy_count = copy_estimate['count']
            copy_ratio = copy_count / target_base_count
            if not target_file_map and copy_count > self.COPY_COUNT_LIMIT:
                self.add_warning(
                    stats,
                    (
                        f'[任务{task_id or "unknown"}] 目标为空，检测到大规模初始化同步: '
                        f'{source_path} -> {target_path}, 计划新增 {copy_count} 项'
                    ),
                )
                return True

            if copy_count > self.COPY_COUNT_LIMIT or (
                target_base_count >= self.RATIO_MIN_BASE and copy_ratio > self.COPY_RATIO_LIMIT
            ):
                self.mark_protection_skip(
                    stats,
                    task_id,
                    (
                        f'本地新增内容超过保护阈值，已跳过: {source_path} -> {target_path}, '
                        f'计划新增 {copy_count} 项，目标当前 {target_base_count} 项'
                    ),
                )
                return False

        if sync_method != 'full' or not target_extra:
            return True

        delete_estimate = await self._estimate_target_delete_changes(
            service,
            target_definition,
            target_path,
            target_id,
            target_file_map,
            target_extra,
            item_filter,
            stats,
            task_id,
            db,
            account_key=account_key,
        )
        if delete_estimate is None:
            self.mark_protection_skip(
                stats,
                task_id,
                f'本地目标删除内容过多或无法估算，已跳过: {target_path}',
            )
            return False

        delete_count = delete_estimate['count']
        delete_ratio = delete_count / target_base_count
        if delete_count > self.DELETE_COUNT_LIMIT or (
            target_base_count >= self.RATIO_MIN_BASE and delete_ratio > self.DELETE_RATIO_LIMIT
        ):
            self.mark_protection_skip(
                stats,
                task_id,
                (
                    f'全量同步计划删除内容超过保护阈值，已跳过: {target_path}, '
                    f'计划删除 {delete_count} 项，目标当前 {target_base_count} 项'
                ),
            )
            return False

        return True

    @staticmethod
    def _is_safe_incremental_file_addition(source_missing: list[str], target_extra: list[str]) -> bool:
        """
        判断是否为可放行的增量新增文件

        :param source_missing: 源端新增项
        :param target_extra: 目标端多余项
        :return:
        """
        if not source_missing or not target_extra:
            return False

        source_missing_all_files = all(not name.endswith('/') for name in source_missing)
        target_extra_all_dirs = all(name.endswith('/') for name in target_extra)
        return source_missing_all_files and target_extra_all_dirs
