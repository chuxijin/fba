#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio
import logging
import posixpath
import time

from collections import defaultdict
from datetime import datetime
from typing import Any

from backend.app.coulddrive.schema.enum import DriveType
from backend.app.coulddrive.schema.file import BaseFileInfo
from backend.app.coulddrive.schema.file import CopyParam
from backend.app.coulddrive.schema.file import ListFilesParam
from backend.app.coulddrive.schema.file import ListShareFilesParam
from backend.app.coulddrive.schema.file import MkdirParam
from backend.app.coulddrive.schema.file import MoveParam
from backend.app.coulddrive.schema.file import RelationshipParam
from backend.app.coulddrive.schema.file import RemoveParam
from backend.app.coulddrive.schema.file import RenameParam
from backend.app.coulddrive.schema.file import TransferParam
from backend.app.coulddrive.schema.file import UserInfoParam
from backend.app.coulddrive.schema.user import BaseUserInfo
from backend.app.coulddrive.service.openlist.api import OpenListApi
from backend.app.coulddrive.service.openlist.errors import OpenListApiError
from backend.app.coulddrive.service.coulddrive_service import BaseDriveClient
from backend.app.coulddrive.service.coulddrive_service import ConfigItem
from backend.app.coulddrive.service.coulddrive_service import ConfigItemType
from backend.app.coulddrive.service.coulddrive_service import DriverRegistry
from backend.app.coulddrive.service.coulddrive_service import DriveAuthError
from backend.core.conf import settings
from backend.utils.timezone import timezone


@DriverRegistry.register(DriveType.OPENLIST_DRIVE)
class OpenListClient(BaseDriveClient):
    """OpenList 网盘客户端"""

    AUTH_ERROR_CODES: set[int] = {401}
    AUTH_ERROR_PATTERNS: tuple[str, ...] = (
        'auth',
        'token',
        '登录',
        '认证',
        '未授权',
        'cookie',
        'authorization',
        'unauthorized',
    )

    @classmethod
    def get_config_items(cls) -> list[ConfigItem]:
        """声明 OpenList 需要的配置项"""
        return [
            ConfigItem(
                name='token',
                label='OpenList Token',
                type=ConfigItemType.PASSWORD,
                required=True,
                description='OpenList 访问令牌，服务地址由环境变量 OPENLIST_BASE_URL 提供',
                placeholder='openlist-token',
            )
        ]

    @classmethod
    def validate_config(cls, config: dict[str, Any]) -> dict[str, list[str]]:
        """
        验证 OpenList 配置

        :param config: 配置字典
        :return:
        """
        result = {'errors': [], 'warnings': []}
        token = str(config.get('token') or config.get('cookie') or '').strip()
        if not token:
            result['errors'].append('需要提供 OpenList Token')
        return result

    def __init__(self, config: str | dict[str, Any], **kwargs):
        """
        初始化 OpenList 驱动

        :param config: 认证配置
        :return:
        """
        super().__init__(config, **kwargs)
        self.logger = logging.getLogger(self.__class__.__name__)

        token = str(self.get_config_value('token', '') or self.get_config_value('cookie', '')).strip()
        if not token:
            raise ValueError('OpenList Token 不能为空')

        self._openlist_api = OpenListApi(token=token)
        self._token = token
        self._is_authorized = True

    def _convert_cookie_to_config(self, cookies: str) -> dict[str, Any]:
        """
        将旧认证字符串转换为 Token 配置

        :param cookies: 旧认证字符串
        :return:
        """
        return {'token': cookies}

    @property
    def drive_type(self) -> str:
        return DriveType.OPENLIST_DRIVE.value

    @property
    def cookies(self) -> str:
        """获取当前 Token"""
        return self._openlist_api.cookies

    def get_current_token(self) -> str:
        """获取当前有效 Token"""
        return self._token

    @staticmethod
    def _normalize_path(path: str | None) -> str:
        """
        规范化 OpenList 路径

        :param path: 原始路径
        :return:
        """
        cleaned = (path or '/').strip().replace('\\', '/')
        if not cleaned:
            return '/'
        if not cleaned.startswith('/'):
            cleaned = f'/{cleaned}'
        normalized = posixpath.normpath(cleaned)
        return normalized if normalized.startswith('/') else f'/{normalized}'

    def _join_path(self, parent_path: str, name: str) -> str:
        """
        拼接完整路径

        :param parent_path: 父目录路径
        :param name: 文件名
        :return:
        """
        parent = self._normalize_path(parent_path)
        child_name = str(name or '').strip().strip('/')
        if not child_name:
            return parent
        if parent == '/':
            return f'/{child_name}'
        return f'{parent}/{child_name}'

    def _get_parent_path(self, path: str) -> str:
        """
        获取父目录路径

        :param path: 完整路径
        :return:
        """
        normalized = self._normalize_path(path)
        if normalized == '/':
            return '/'
        parent = posixpath.dirname(normalized)
        return parent or '/'

    def _get_name(self, path: str) -> str:
        """
        获取文件名

        :param path: 完整路径
        :return:
        """
        normalized = self._normalize_path(path)
        if normalized == '/':
            return ''
        return posixpath.basename(normalized)

    @staticmethod
    def _ensure_path_list(paths: str | list[str] | None) -> list[str]:
        """
        将路径参数统一转换为列表

        :param paths: 路径参数
        :return:
        """
        if paths is None:
            return []
        if isinstance(paths, str):
            return [paths]
        return [str(path) for path in paths if path]

    def _build_file_info(self, parent_path: str, item: dict[str, Any]) -> BaseFileInfo:
        """
        将 OpenList 原始文件对象转换为统一文件模型

        :param parent_path: 父目录路径
        :param item: OpenList 文件对象
        :return:
        """
        file_name = str(item.get('name') or '')
        file_path = self._join_path(parent_path, file_name)
        return BaseFileInfo(
            file_id=file_path,
            file_name=file_name,
            file_path=file_path,
            file_size=item.get('size', 0),
            is_folder=bool(item.get('is_dir', False)),
            created_at=self._normalize_datetime(item.get('created')),
            updated_at=self._normalize_datetime(item.get('modified')),
            parent_id=self._normalize_path(parent_path),
            file_ext={
                'hash_info': item.get('hash_info'),
                'provider': item.get('provider'),
                'raw': item,
            },
        )

    @staticmethod
    def _normalize_datetime(value: Any) -> str:
        """
        规范化 OpenList 时间字段

        :param value: OpenList 原始时间值
        :return:
        """
        if not value:
            return ''

        text = str(value).strip()
        if not text:
            return ''

        if text in {'0', '0.0'}:
            return ''

        try:
            timestamp = float(text)
            if timestamp <= 0:
                return ''

            date = datetime.fromtimestamp(
                timestamp / 1000 if timestamp > 9_999_999_999 else timestamp
            )
            if date.year <= 1971:
                return ''

            return text
        except ValueError:
            pass

        try:
            date = datetime.fromisoformat(text.replace('Z', '+00:00'))
            if date.year <= 1971:
                return ''
        except ValueError:
            return text

        return text

    async def _list_directory(self, directory_path: str, refresh: bool = False) -> list[dict[str, Any]]:
        """
        获取目录内容

        :param directory_path: 目录路径
        :param refresh: 是否刷新
        :return:
        """
        result = await self._openlist_api.list(file_path=directory_path, page=1, num=0, refresh=refresh)
        content = result.get('content') if isinstance(result, dict) else None
        if not content:
            return []
        return [item for item in content if isinstance(item, dict)]

    async def _find_item(self, file_path: str, refresh: bool = False) -> dict[str, Any] | None:
        """
        根据完整路径查找文件项

        :param file_path: 完整路径
        :param refresh: 是否刷新目录缓存
        :return:
        """
        normalized_path = self._normalize_path(file_path)
        if normalized_path == '/':
            return {
                'name': '',
                'size': 0,
                'is_dir': True,
                'created': '',
                'modified': '',
            }

        parent_path = self._get_parent_path(normalized_path)
        file_name = self._get_name(normalized_path)
        items = await self._list_directory(parent_path, refresh=refresh)
        for item in items:
            if str(item.get('name') or '') == file_name:
                return item
        return None

    def _group_names_by_parent(self, file_paths: list[str]) -> dict[str, list[str]]:
        """
        按父目录分组文件名

        :param file_paths: 完整路径列表
        :return:
        """
        groups: dict[str, list[str]] = defaultdict(list)
        for path in file_paths:
            normalized_path = self._normalize_path(path)
            groups[self._get_parent_path(normalized_path)].append(self._get_name(normalized_path))
        return dict(groups)

    async def get_user_info(self, params: UserInfoParam | None = None, **kwargs) -> BaseUserInfo:
        """
        获取用户信息

        :param params: 用户信息参数
        :return:
        """
        try:
            account_info = await self._openlist_api.get_account_info()
            username = str(account_info.get('username') or account_info.get('display_name') or 'OpenList User')
            permission = account_info.get('permission', 0)
            is_admin = bool(account_info.get('is_admin')) or permission not in [0, '0', None]

            return BaseUserInfo(
                user_id=str(account_info.get('id') or username),
                username=username,
                avatar_url='',
                quota=None,
                used=None,
                is_vip=is_admin,
                is_supervip=is_admin,
            )
        except Exception as e:
            if self._is_auth_error(e):
                raise DriveAuthError(str(e), drive_type=self.drive_type) from e
            self.logger.error(f'获取 OpenList 用户信息失败: {e}')
            return BaseUserInfo(user_id='0', username='未知用户', avatar_url='', is_vip=False, is_supervip=False)

    async def get_disk_list(self, params: ListFilesParam, **kwargs: Any) -> list[BaseFileInfo]:
        """
        获取目录文件列表

        :param params: 列表参数
        :return:
        """
        directory_path = self._normalize_path(params.file_path or '/')
        try:
            items = await self._list_directory(directory_path, refresh=False)
            return [self._build_file_info(directory_path, item) for item in items]
        except Exception as e:
            if self._is_auth_error(e):
                raise DriveAuthError(str(e), drive_type=self.drive_type) from e
            self.logger.error(f'获取 OpenList 文件列表失败: {directory_path}, 错误: {e}')
            raise OpenListApiError(f'获取 OpenList 文件列表失败: {e}', cause=e) from e

    async def mkdir(self, params: MkdirParam, **kwargs: Any) -> BaseFileInfo:
        """
        创建目录

        :param params: 创建目录参数
        :return:
        """
        file_name = str(params.file_name or '').strip()
        if file_name:
            parent_path = self._normalize_path(params.parent_id or params.file_path or '/')
            full_path = self._join_path(parent_path, file_name)
        else:
            full_path = self._normalize_path(params.file_path)
            parent_path = self._get_parent_path(full_path)
            file_name = self._get_name(full_path)

        if not file_name:
            raise OpenListApiError('创建 OpenList 目录失败: 缺少目录名称')

        try:
            if params.return_if_exist:
                existing_item = await self._find_item(full_path)
                if existing_item and existing_item.get('is_dir'):
                    return self._build_file_info(parent_path, existing_item)

            await self._openlist_api.mkdir(path=full_path)

            created_item = await self._find_item(full_path, refresh=True)
            if created_item:
                return self._build_file_info(parent_path, created_item)

            now = timezone.now().isoformat()
            return BaseFileInfo(
                file_id=full_path,
                file_name=file_name,
                file_path=full_path,
                file_size=0,
                is_folder=True,
                created_at=now,
                updated_at=now,
                parent_id=parent_path,
            )
        except Exception as e:
            if self._is_auth_error(e):
                raise DriveAuthError(str(e), drive_type=self.drive_type) from e
            self.logger.error(f'创建 OpenList 目录失败: {full_path}, 错误: {e}')
            raise OpenListApiError(f'创建 OpenList 目录失败: {e}', cause=e) from e

    async def rename(self, params: RenameParam, **kwargs: Any) -> bool:
        """
        重命名文件或目录

        :param params: 重命名参数
        :return:
        """
        source_path = self._normalize_path(
            params.file_path or self._join_path(params.parent_id or '/', params.file_name or '')
        )
        if source_path == '/' or not self._get_name(source_path):
            self.logger.error('OpenList 重命名失败: 缺少原始文件路径')
            return False

        target_path = self._normalize_path(
            params.new_path or self._join_path(self._get_parent_path(source_path), params.new_name)
        )
        target_name = params.new_name or self._get_name(target_path)
        if not target_name:
            self.logger.error('OpenList 重命名失败: 缺少目标文件名')
            return False

        source_parent = self._get_parent_path(source_path)
        target_parent = self._get_parent_path(target_path)
        source_name = self._get_name(source_path)

        try:
            if source_parent != target_parent:
                move_result = await self._openlist_api.move(
                    src_dir=source_parent,
                    dst_dir=target_parent,
                    names=[source_name],
                )
                if not await self._wait_copy_tasks(move_result, operation_name='移动'):
                    return False
                source_path = self._join_path(target_parent, source_name)

            if self._get_name(source_path) == target_name:
                return True

            await self._openlist_api.rename(path=source_path, name=target_name)
            return True
        except Exception as e:
            if self._is_auth_error(e):
                raise DriveAuthError(str(e), drive_type=self.drive_type) from e
            self.logger.error(f'OpenList 重命名失败: {source_path} -> {target_path}, 错误: {e}')
            return False

    async def move(self, params: MoveParam, **kwargs: Any) -> bool:
        """
        移动文件或目录

        :param params: 移动参数
        :return:
        """
        file_paths = self._ensure_path_list(params.file_paths) or self._ensure_path_list(params.file_ids)
        target_raw_path = params.target_path or params.target_id
        if not file_paths or not target_raw_path:
            self.logger.error('OpenList 移动失败: 缺少源路径或目标路径')
            return False
        target_path = self._normalize_path(target_raw_path)

        grouped_paths = self._group_names_by_parent(file_paths)
        try:
            for source_parent, names in grouped_paths.items():
                move_result = await self._openlist_api.move(src_dir=source_parent, dst_dir=target_path, names=names)
                if not await self._wait_copy_tasks(move_result, operation_name='移动'):
                    return False
            return True
        except Exception as e:
            if self._is_auth_error(e):
                raise DriveAuthError(str(e), drive_type=self.drive_type) from e
            self.logger.error(f'OpenList 移动失败: {file_paths} -> {target_path}, 错误: {e}')
            return False

    async def copy(self, params: CopyParam, **kwargs: Any) -> bool:
        """
        复制文件或目录

        :param params: 复制参数
        :return:
        """
        file_paths = self._ensure_path_list(params.file_paths) or self._ensure_path_list(params.file_ids)
        target_raw_path = params.target_path or params.target_id
        if not file_paths or not target_raw_path:
            self.logger.error('OpenList 复制失败: 缺少源路径或目标路径')
            return False
        target_path = self._normalize_path(target_raw_path)

        grouped_paths = self._group_names_by_parent(file_paths)
        try:
            for source_parent, names in grouped_paths.items():
                copy_result = await self._openlist_api.copy(src_dir=source_parent, dst_dir=target_path, names=names)
                if not await self._wait_copy_tasks(copy_result, operation_name='复制'):
                    return False
            return True
        except Exception as e:
            if self._is_auth_error(e):
                raise DriveAuthError(str(e), drive_type=self.drive_type) from e
            self.logger.error(f'OpenList 复制失败: {file_paths} -> {target_path}, 错误: {e}')
            return False

    async def remove(self, params: RemoveParam, **kwargs: Any) -> bool:
        """
        删除文件或目录

        :param params: 删除参数
        :return:
        """
        file_paths = self._ensure_path_list(params.file_paths) or self._ensure_path_list(params.file_ids)
        if not file_paths and params.parent_id and params.file_name:
            file_paths = [self._join_path(params.parent_id, params.file_name)]

        if not file_paths:
            self.logger.error('OpenList 删除失败: 缺少文件路径')
            return False

        grouped_paths = self._group_names_by_parent(file_paths)
        try:
            for parent_path, names in grouped_paths.items():
                await self._openlist_api.remove(names=names, dir=parent_path)
            return True
        except Exception as e:
            if self._is_auth_error(e):
                raise DriveAuthError(str(e), drive_type=self.drive_type) from e
            self.logger.error(f'OpenList 删除失败: {file_paths}, 错误: {e}')
            return False

    async def transfer(self, params: TransferParam, **kwargs: Any) -> bool:
        """
        OpenList 不支持分享直转存

        :param params: 转存参数
        :return:
        """
        self.logger.warning(
            'OpenList 不支持直接转存分享源，source_type=%s, source_id=%s',
            params.source_type,
            params.source_id,
        )
        return False

    async def get_share_list(self, params: ListShareFilesParam, **kwargs: Any) -> list[BaseFileInfo]:
        """
        获取分享文件列表

        :param params: 分享列表参数
        :return:
        """
        list_params = ListFilesParam(file_path=params.file_path, drive_type=params.drive_type)
        try:
            return await self.get_disk_list(list_params, **kwargs)
        except DriveAuthError:
            raise
        except Exception as e:
            self.logger.error(f'获取 OpenList 分享文件列表失败: {e}')
            return []

    async def get_relationship_list(self, params: RelationshipParam, **kwargs: Any) -> list[Any]:
        """OpenList 不支持关系功能"""
        return []

    def _extract_copy_task_ids(self, result: dict[str, Any] | None) -> list[str]:
        """
        从 OpenList 复制响应中提取任务 ID

        :param result: OpenList 复制响应
        :return:
        """
        if not result:
            return []

        tasks = result.get('tasks')
        if not isinstance(tasks, list):
            return []

        task_ids: list[str] = []
        for task in tasks:
            if not isinstance(task, dict):
                continue
            task_id = task.get('id')
            if task_id:
                task_ids.append(str(task_id))
        return task_ids

    async def _wait_copy_tasks(self, result: dict[str, Any] | None, operation_name: str) -> bool:
        """
        等待 OpenList 异步复制任务结束

        :param result: OpenList 复制响应
        :param operation_name: 操作名称
        :return:
        """
        task_ids = self._extract_copy_task_ids(result)
        if not task_ids:
            return True

        for task_id in task_ids:
            if not await self._wait_copy_task(task_id, operation_name):
                return False
        return True

    async def _wait_copy_task(self, task_id: str, operation_name: str) -> bool:
        """
        等待单个 OpenList 复制任务结束

        :param task_id: OpenList 任务 ID
        :param operation_name: 操作名称
        :return:
        """
        timeout_seconds = settings.OPENLIST_TASK_WAIT_TIMEOUT
        poll_interval = settings.OPENLIST_TASK_POLL_INTERVAL
        deadline = time.monotonic() + timeout_seconds
        last_progress: Any = None

        while time.monotonic() < deadline:
            try:
                task_info = await self._openlist_api.copy_task_info(task_id)
            except Exception as e:
                if self._is_auth_error(e):
                    raise DriveAuthError(str(e), drive_type=self.drive_type) from e
                self.logger.error(f'OpenList {operation_name}任务查询失败: {task_id}, 错误: {e}')
                return False

            state = task_info.get('state')
            progress = task_info.get('progress')
            error = task_info.get('error')
            state_code = str(state)
            if progress != last_progress:
                self.logger.info(
                    f'OpenList {operation_name}任务进度: task_id={task_id}, state={state}, progress={progress}'
                )
                last_progress = progress

            if state_code == '2':
                await self._delete_finished_copy_task(task_id)
                return True

            if state_code in ['4', '7']:
                await self._delete_finished_copy_task(task_id)
                self.logger.error(f'OpenList {operation_name}任务失败: task_id={task_id}, state={state}, error={error}')
                return False

            await asyncio.sleep(poll_interval)

        self.logger.error(f'OpenList {operation_name}任务等待超时: task_id={task_id}, timeout={timeout_seconds}s')
        return False

    async def _delete_finished_copy_task(self, task_id: str) -> None:
        """
        删除已结束的 OpenList 复制任务记录

        :param task_id: OpenList 任务 ID
        :return:
        """
        try:
            await self._openlist_api.copy_task_delete(task_id)
        except Exception as e:
            self.logger.warning(f'删除 OpenList 复制任务记录失败: task_id={task_id}, 错误: {e}')
