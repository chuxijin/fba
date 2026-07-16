#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
from collections.abc import Iterable

import pytest

from backend.app.mydrive.service.filesystem.exceptions import InvalidTransferError
from backend.app.mydrive.service.filesystem.models import FileObject, SpaceLocator, SpaceType
from backend.app.mydrive.service.filesystem.spaces import TransferSource, WritableFileSpace
from backend.app.mydrive.service.transfer_service import transfer_files


class FakeLinkSpace(TransferSource):
    """链接文件空间。"""

    def __init__(self) -> None:
        """初始化链接文件空间。"""
        self._locator = SpaceLocator(provider='baidu', space_type=SpaceType.SHARE_LINK, source_id='share-1')

    @property
    def locator(self) -> SpaceLocator:
        """获取链接空间定位信息。"""
        return self._locator

    async def list(self, directory: FileObject | None = None) -> list[FileObject]:
        """
        列出链接文件。

        :param directory: 待列出的目录
        :return: 文件对象列表
        """
        return []

    async def get(self, file_id: str) -> FileObject | None:
        """
        获取链接文件。

        :param file_id: 文件唯一标识
        :return: 文件对象
        """
        return None

    async def transfer_to(self, files: Iterable[FileObject], target: WritableFileSpace) -> list[FileObject]:
        """
        转存链接文件。

        :param files: 待转存文件
        :param target: 目标空间
        :return: 目标文件列表
        """
        return [
            FileObject(
                space=target.locator,
                file_id='target-file-1',
                name=file.name,
                path=f'/{file.name}',
            )
            for file in files
        ]


class FakePersonalSpace(WritableFileSpace):
    """个人文件空间。"""

    def __init__(self, space_type: SpaceType = SpaceType.PERSONAL) -> None:
        """
        初始化个人文件空间。

        :param space_type: 文件空间类型
        """
        self._locator = SpaceLocator(provider='baidu', space_type=space_type, account_id='account-1')

    @property
    def locator(self) -> SpaceLocator:
        """获取个人空间定位信息。"""
        return self._locator

    async def list(self, directory: FileObject | None = None) -> list[FileObject]:
        """
        列出个人文件。

        :param directory: 待列出的目录
        :return: 文件对象列表
        """
        return []

    async def get(self, file_id: str) -> FileObject | None:
        """
        获取个人文件。

        :param file_id: 文件唯一标识
        :return: 文件对象
        """
        return None

    async def make_directory(self, name: str, parent: FileObject | None = None) -> FileObject:
        """
        创建目录。

        :param name: 目录名称
        :param parent: 父目录
        :return: 目录对象
        """
        return FileObject(space=self.locator, file_id=name, name=name, path=f'/{name}', is_directory=True)

    async def copy(self, files: Iterable[FileObject], target: FileObject | None = None) -> None:
        """
        复制文件。

        :param files: 待复制对象
        :param target: 目标目录
        :return:
        """

    async def move(self, files: Iterable[FileObject], target: FileObject | None = None) -> None:
        """
        移动文件。

        :param files: 待移动对象
        :param target: 目标目录
        :return:
        """

    async def rename(self, file: FileObject, new_name: str) -> FileObject:
        """
        重命名文件。

        :param file: 待重命名对象
        :param new_name: 新名称
        :return: 重命名后的对象
        """
        return FileObject(space=self.locator, file_id=file.file_id, name=new_name, path=f'/{new_name}')

    async def remove(self, files: Iterable[FileObject]) -> None:
        """
        删除文件。

        :param files: 待删除对象
        :return:
        """


def test_transfer_files_allows_share_link_to_personal_space() -> None:
    """链接文件应能单向转存至个人空间。"""
    source = FakeLinkSpace()
    target = FakePersonalSpace()
    source_file = FileObject(space=source.locator, file_id='source-file-1', name='course.pdf', path='/course.pdf')

    transferred_files = asyncio.run(transfer_files(source, [source_file], target))

    assert [file.file_id for file in transferred_files] == ['target-file-1']
    assert transferred_files[0].space == target.locator


def test_transfer_files_allows_share_link_to_openlist_space() -> None:
    """链接文件应能单向转存至 OpenList 空间。"""
    source = FakeLinkSpace()
    target = FakePersonalSpace(space_type=SpaceType.OPENLIST)
    source_file = FileObject(space=source.locator, file_id='source-file-1', name='course.pdf', path='/course.pdf')

    transferred_files = asyncio.run(transfer_files(source, [source_file], target))

    assert transferred_files[0].space == target.locator


def test_transfer_files_rejects_personal_space_as_source() -> None:
    """个人空间不能作为外部单向同步源。"""
    source = FakeLinkSpace()
    source._locator = SpaceLocator(provider='baidu', space_type=SpaceType.PERSONAL, account_id='account-2')
    target = FakePersonalSpace()

    with pytest.raises(InvalidTransferError, match='外部同步源'):
        asyncio.run(transfer_files(source, [], target))


def test_transfer_files_rejects_share_link_as_target() -> None:
    """链接空间不能作为同步目标。"""
    source = FakeLinkSpace()
    target = FakePersonalSpace(space_type=SpaceType.SHARE_LINK)

    with pytest.raises(InvalidTransferError, match='同步目标'):
        asyncio.run(transfer_files(source, [], target))
