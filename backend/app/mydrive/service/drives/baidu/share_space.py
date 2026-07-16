#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Iterable
from dataclasses import replace
from pathlib import PurePosixPath
from typing import Any

from backend.app.mydrive.service.drives.baidu.client import BaiduRequest
from backend.app.mydrive.service.drives.baidu.personal_space import BaiduPersonalSpace
from backend.app.mydrive.service.drives.baidu.types import build_baidu_file
from backend.app.mydrive.service.filesystem.models import FileObject, SpaceLocator, SpaceType
from backend.app.mydrive.service.filesystem.spaces import TransferSource, WritableFileSpace


class BaiduShareSpace(TransferSource):
    """百度分享文件空间。"""

    def __init__(
        self,
        account_id: int,
        cookie: str,
        url: str,
        passcode: str = '',
        root_id: str = '',
        root_path: str = '/',
        sekey: str = '',
        bdstoken: str = '',
        client: BaiduRequest | None = None,
    ) -> None:
        """
        初始化百度分享文件空间。

        :param account_id: MyDrive 账户 ID
        :param cookie: 百度网盘 Cookie
        :param url: 分享链接
        :param passcode: 分享提取码
        :param root_id: 分享根目录 ID
        :param root_path: 分享根目录路径
        :param sekey: 分享页面会话密钥
        :param bdstoken: 分享页面操作令牌
        :param client: 百度请求封装
        """
        self._locator = SpaceLocator(
            provider='baidu',
            space_type=SpaceType.SHARE_LINK,
            account_id=str(account_id),
            source_id=url,
            root_path=root_path,
        )
        self._client = client or BaiduRequest(cookie)
        self._passcode = passcode
        self._root_id = root_id
        self._sekey = sekey
        self._bdstoken = bdstoken
        self._context: dict | None = None
        self._root_files: list[dict] | None = None
        self._share_base_path: str | None = None
        self._mounted_remote_root_path: str | None = None
        self._files: dict[str, FileObject] = {}

    @property
    def locator(self) -> SpaceLocator:
        """获取百度分享文件空间定位信息。"""
        return self._locator

    async def aclose(self) -> None:
        """关闭百度分享文件空间资源。"""
        await self._client.aclose()

    async def list(self, directory: FileObject | None = None) -> list[FileObject]:
        """
        列出百度分享目录内容。

        :param directory: 待列出的目录，为空时列出分享根目录
        :return:
        """
        context, root_files = await self._get_root()
        mounted_remote_root_path = self._get_mounted_remote_root_path(context, root_files)
        virtual_directory_path = directory.path if directory is not None else '/'
        if directory is None:
            if self.locator.root_path == '/':
                items = root_files
                remote_directory_path = self._get_share_base_path(context, root_files)
            else:
                items = await self._client.list_share_files(context, mounted_remote_root_path)
                remote_directory_path = mounted_remote_root_path
        else:
            remote_path = self._get_remote_directory_path(directory, mounted_remote_root_path)
            items = await self._client.list_share_files(context, remote_path)
            remote_directory_path = remote_path
        files = [
            self._build_virtual_file(item, context, mounted_remote_root_path, remote_directory_path, virtual_directory_path)
            for item in items
        ]
        self._files.update({file.file_id: file for file in files})
        return files

    @staticmethod
    def _get_remote_directory_path(directory: FileObject, mounted_remote_root_path: str) -> str:
        """获取百度分享目录的原始路径。"""
        remote_path = str(directory.extra.get('remote_path') or '')
        if remote_path:
            return remote_path
        root_path = directory.space.root_path.rstrip('/')
        virtual_path = directory.path
        if root_path and virtual_path.startswith(f'{root_path}/'):
            virtual_path = virtual_path.removeprefix(root_path)
        return str(PurePosixPath(mounted_remote_root_path) / virtual_path.lstrip('/'))

    def _get_mounted_remote_root_path(self, context: dict[str, Any], root_files: list[dict[str, Any]]) -> str:
        """获取百度分享挂载根目录的原始路径。"""
        if self._mounted_remote_root_path is not None:
            return self._mounted_remote_root_path
        share_base_path = self._get_share_base_path(context, root_files)
        configured_root_path = self.locator.root_path.rstrip('/') or '/'
        if configured_root_path == '/':
            self._mounted_remote_root_path = share_base_path
            return self._mounted_remote_root_path
        self._mounted_remote_root_path = str(PurePosixPath(share_base_path) / configured_root_path.lstrip('/'))
        return self._mounted_remote_root_path

    def _get_share_base_path(self, context: dict[str, Any], root_files: list[dict[str, Any]]) -> str:
        """获取百度分享页面根目录的原始路径。"""
        if self._share_base_path is not None:
            return self._share_base_path
        if self._root_id and context.get('uk'):
            self._share_base_path = f'/sharelink{context["uk"]}-{self._root_id}'
            return self._share_base_path
        if not root_files:
            self._share_base_path = '/'
            return self._share_base_path
        first_path = str(root_files[0].get('path') or '')
        self._share_base_path = str(PurePosixPath(first_path).parent)
        return self._share_base_path

    def _build_virtual_file(
        self,
        item: dict[str, Any],
        context: dict[str, Any],
        remote_root_path: str,
        remote_directory_path: str | None = None,
        virtual_directory_path: str = '/',
    ) -> FileObject:
        """将百度分享原始文件转换为挂载内虚拟文件。"""
        file = build_baidu_file(self.locator, item, extra={'share_context': context})
        remote_path = file.path
        if remote_directory_path and not remote_path.startswith(f'{remote_root_path}/'):
            remote_path = str(PurePosixPath(remote_directory_path) / file.name)
        virtual_path = remote_path.removeprefix(remote_root_path).strip('/')
        if remote_path == file.path and not virtual_path and file.name:
            virtual_path = str(PurePosixPath(virtual_directory_path) / file.name).strip('/')
        path = f'/{virtual_path}' if virtual_path else '/'
        return replace(file, path=path, extra={**file.extra, 'remote_path': remote_path})

    async def get(self, file_id: str) -> FileObject | None:
        """
        获取已读取的百度分享文件对象。

        :param file_id: 文件唯一标识
        :return:
        """
        return self._files.get(file_id)

    async def transfer_to(
        self,
        files: Iterable[FileObject],
        target: WritableFileSpace,
        target_directory: FileObject | None = None,
    ) -> list[FileObject]:
        """
        将百度分享文件转存到百度个人空间。

        :param files: 待转存文件
        :param target: 可写目标空间
        :param target_directory: 目标目录
        :return:
        """
        if not isinstance(target, BaiduPersonalSpace):
            raise ValueError('百度分享文件只能转存到百度个人空间')
        file_list = list(files)
        if not file_list:
            return []
        context, _ = await self._get_root()
        target_path = target_directory.path if target_directory is not None else target.locator.root_path
        await self._client.save_share_files(context, [file.file_id for file in file_list], target_path)
        return await target.resolve_transferred_files(file_list, target_directory)

    async def _get_root(self) -> tuple[dict, list[dict]]:
        """获取并缓存分享根目录上下文。"""
        if self._context is None or self._root_files is None:
            self._context, self._root_files = await self._client.get_share_root(self.locator.source_id or '', self._passcode)
            if self._sekey:
                self._context['sekey'] = self._sekey
            if self._bdstoken:
                self._context['bdstoken'] = self._bdstoken
        return self._context, self._root_files
