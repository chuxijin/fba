#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from collections.abc import Iterable

from backend.app.mydrive.service.filesystem.models import FileObject, SpaceLocator, SpaceType
from backend.app.mydrive.service.filesystem.spaces import TransferSource, WritableFileSpace
from backend.app.mydrive.service.drives.quark.client import QuarkRequest
from backend.app.mydrive.service.drives.quark.personal_space import QuarkPersonalSpace
from backend.app.mydrive.service.drives.quark.types import build_quark_file


class QuarkShareSpace(TransferSource):
    """夸克分享文件空间。"""

    def __init__(
        self,
        account_id: int,
        cookie: str,
        share_id: str,
        passcode: str = '',
        root_id: str = '0',
        root_path: str = '/',
        client: QuarkRequest | None = None,
    ) -> None:
        """
        初始化夸克分享文件空间。

        :param account_id: MyDrive 账户 ID
        :param cookie: 夸克网盘 Cookie
        :param share_id: 分享标识
        :param passcode: 分享提取码
        :param root_id: 分享根目录 ID
        :param root_path: 分享根目录路径
        :param client: 夸克请求封装
        """
        self._locator = SpaceLocator(
            provider='quark',
            space_type=SpaceType.SHARE_LINK,
            account_id=str(account_id),
            source_id=share_id,
            root_id=root_id,
            root_path=root_path,
        )
        self._client = client or QuarkRequest(cookie)
        self._passcode = passcode
        self._files: dict[str, FileObject] = {}
        self._token: str | None = None

    @property
    def locator(self) -> SpaceLocator:
        """获取夸克分享文件空间定位信息。"""
        return self._locator

    async def aclose(self) -> None:
        """关闭夸克分享文件空间资源。"""
        await self._client.aclose()

    async def list(self, directory: FileObject | None = None) -> list[FileObject]:
        """
        列出夸克分享目录内容。

        :param directory: 待列出的目录，为空时列出分享根目录
        :return:
        """
        token = await self._get_token()
        parent_id = directory.file_id if directory is not None else self.locator.root_id or '0'
        parent_path = directory.path if directory is not None else self.locator.root_path
        items = await self._client.list_share_files(self.locator.source_id or '', token, parent_id)
        files = [
            build_quark_file(
                self.locator,
                item,
                parent_path,
                extra={
                    'share_parent_id': parent_id,
                    'share_file_token': item.get('share_fid_token'),
                },
            )
            for item in items
        ]
        self._files.update({file.file_id: file for file in files})
        return files

    async def get(self, file_id: str) -> FileObject | None:
        """
        获取已读取的分享文件对象。

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
        将夸克分享文件转存到夸克个人空间。

        :param files: 待转存文件
        :param target: 可写目标空间
        :param target_directory: 目标目录
        :return:
        """
        if not isinstance(target, QuarkPersonalSpace):
            raise ValueError('夸克分享文件只能转存到夸克个人空间')

        file_list = list(files)
        if not file_list:
            return []

        parent_ids = {str(file.extra.get('share_parent_id') or '') for file in file_list}
        if len(parent_ids) != 1 or not next(iter(parent_ids)):
            raise ValueError('转存文件必须位于同一个分享目录')

        file_tokens = [str(file.extra.get('share_file_token') or '') for file in file_list]
        if any(not file_token for file_token in file_tokens):
            raise ValueError('分享文件缺少转存凭证，请重新浏览目录')

        await self._client.save_share_files(
            share_id=self.locator.source_id or '',
            token=await self._get_token(),
            parent_id=next(iter(parent_ids)),
            file_ids=[file.file_id for file in file_list],
            file_tokens=file_tokens,
            target_id=target_directory.file_id if target_directory is not None else target.locator.root_id or '0',
        )
        return await target.resolve_transferred_files(file_list, target_directory)

    async def _get_token(self) -> str:
        """获取并缓存分享访问令牌。"""
        if self._token is None:
            self._token = await self._client.get_share_token(self.locator.source_id or '', self._passcode)
        return self._token
