#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Iterable

from backend.app.mydrive.service.drives.baidu.client import BaiduRequest
from backend.app.mydrive.service.drives.baidu.personal_space import BaiduPersonalSpace
from backend.app.mydrive.service.drives.baidu.types import build_baidu_file
from backend.app.mydrive.service.filesystem.models import FileObject, SpaceLocator, SpaceType
from backend.app.mydrive.service.filesystem.spaces import TransferSource, WritableFileSpace


class BaiduRelationshipSpace(TransferSource):
    """百度好友或群组分享空间。"""

    def __init__(
        self,
        account_id: int,
        cookie: str,
        space_type: SpaceType,
        source_id: str,
        from_uk: str,
        message_id: str,
        root_id: str,
        root_path: str = '/',
        client: BaiduRequest | None = None,
    ) -> None:
        """
        初始化百度关系分享空间。

        :param account_id: MyDrive 账户 ID
        :param cookie: 百度网盘 Cookie
        :param space_type: 好友或群组空间类型
        :param source_id: 好友 UK 或群组 ID
        :param from_uk: 分享者 UK
        :param message_id: 分享消息 ID
        :param root_id: 分享根文件 ID
        :param root_path: 挂载根目录路径
        :param client: 百度请求封装
        :return:
        """
        if space_type not in {SpaceType.FRIEND, SpaceType.GROUP}:
            raise ValueError('百度关系空间类型仅支持 friend 或 group')
        self._locator = SpaceLocator(
            provider='baidu', space_type=space_type, account_id=str(account_id), source_id=source_id,
            root_id=root_id, root_path=root_path,
            extra={'from_uk': from_uk, 'message_id': message_id},
        )
        self._client = client or BaiduRequest(cookie)
        self._files: dict[str, FileObject] = {}

    @property
    def locator(self) -> SpaceLocator:
        """获取百度关系空间定位信息。"""
        return self._locator

    async def aclose(self) -> None:
        """关闭百度关系空间资源。"""
        await self._client.aclose()

    async def list(self, directory: FileObject | None = None) -> list[FileObject]:
        """
        列出百度关系分享目录内容。

        :param directory: 待列出的目录
        :return:
        """
        file_id = directory.file_id if directory is not None else self.locator.root_id or ''
        items = await self._client.list_relationship_share_files(
            space_type=self.locator.space_type.value,
            source_id=self.locator.source_id or '',
            from_uk=str(self.locator.extra['from_uk']),
            message_id=str(self.locator.extra['message_id']),
            file_id=file_id,
        )
        files = [
            build_baidu_file(
                self.locator,
                item,
                extra={'from_uk': self.locator.extra['from_uk'], 'message_id': self.locator.extra['message_id']},
            )
            for item in items
        ]
        self._files.update({file.file_id: file for file in files})
        return files

    async def get(self, file_id: str) -> FileObject | None:
        """获取已读取的关系分享文件对象。"""
        return self._files.get(file_id)

    async def transfer_to(
        self,
        files: Iterable[FileObject],
        target: WritableFileSpace,
        target_directory: FileObject | None = None,
    ) -> list[FileObject]:
        """
        转存百度好友或群组分享文件。

        :param files: 待转存文件
        :param target: 目标个人空间
        :param target_directory: 目标目录
        :return:
        """
        if not isinstance(target, BaiduPersonalSpace):
            raise ValueError('百度好友或群组分享只能转存到百度个人空间')
        file_list = list(files)
        if not file_list:
            return []
        target_path = target_directory.path if target_directory is not None else target.locator.root_path
        await self._client.transfer_relationship_files(
            space_type=self.locator.space_type.value,
            source_id=self.locator.source_id or '',
            from_uk=str(self.locator.extra['from_uk']),
            message_id=str(self.locator.extra['message_id']),
            file_ids=[file.file_id for file in file_list],
            target_path=target_path,
        )
        return await target.resolve_transferred_files(file_list, target_directory)
