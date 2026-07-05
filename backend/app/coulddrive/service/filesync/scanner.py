#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.coulddrive.schema.file import ListFilesParam
from backend.app.coulddrive.schema.file import ListShareFilesParam
from backend.app.coulddrive.service.coulddrive_service import CouldDriveService
from backend.app.coulddrive.service.rule_template_service import ItemFilter


class FileSyncScanner:
    """文件同步扫描器"""

    def __init__(self, *, logger: Any) -> None:
        """
        初始化文件同步扫描器

        :param logger: 日志对象
        :return:
        """
        self._logger = logger

    async def list_dir(
        self,
        service: CouldDriveService,
        path: str,
        first_dst: bool,
        item_filter: ItemFilter | None,
        is_src: bool,
        definition: Any,
        target_id: str | None = None,
        task_id: int | None = None,
        db: AsyncSession | None = None,
        **kwargs,
    ) -> dict[str, dict[str, Any]]:
        """
        列出目录并转换为同步文件映射

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
        try:
            drive_type = await service.get_drive_type()
            if is_src and getattr(definition, 'source_type', '') != 'local':
                params = ListShareFilesParam(
                    drive_type=drive_type,
                    source_type=definition.source_type,
                    source_id=definition.source_id,
                    file_path=path,
                )
                files = await service.get_share_list(params=params, db=db, **kwargs)
            else:
                params = ListFilesParam(
                    drive_type=drive_type,
                    file_path=path,
                    file_id=target_id or '',
                    desc=False,
                    name=False,
                    time=False,
                    size_sort=False,
                )
                files = await service.get_disk_list(params=params, db=db, **kwargs)

            file_map: dict[str, dict[str, Any]] = {}
            for file in files:
                if item_filter and item_filter.should_exclude(file):
                    self._logger.debug(f'[任务{task_id or "unknown"}] 文件被过滤器排除: {file.file_name}')
                    continue

                file_name = file.file_name + '/' if getattr(file, 'is_folder', False) else file.file_name
                file_size = file.file_size if not getattr(file, 'is_folder', False) else 0
                file_info = {
                    'file_size': file_size,
                    'file_id': file.file_id,
                }

                if is_src and hasattr(file, 'file_ext') and file.file_ext:
                    file_info.update(file.file_ext)

                file_map[file_name] = file_info

            return file_map

        except Exception as e:
            error_msg = f'扫描目录失败: {path}, 错误: {str(e)}'
            self._logger.error(f'[任务{task_id or "unknown"}] {error_msg}', exc_info=True)
            raise e
