#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
from collections.abc import Iterable

import pytest

from backend.app.mydrive.service.filesystem.exceptions import InvalidTransferError, TransferBatchLimitError
from backend.app.mydrive.service.filesystem.models import FileObject, SpaceLocator, SpaceType
from backend.app.mydrive.service.filesystem.spaces import TransferSource, WritableFileSpace
from backend.app.mydrive.service.transfer_service import transfer_files


class FakeLinkSpace(TransferSource):
    """链接文件空间。"""

    def __init__(self) -> None:
        """初始化链接文件空间。"""
        self._locator = SpaceLocator(provider='baidu', space_type=SpaceType.SHARE_LINK, source_id='share-1')
        self.transfer_batch_sizes: list[int] = []

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

    async def transfer_to(
        self,
        files: Iterable[FileObject],
        target: WritableFileSpace,
        target_directory: FileObject | None = None,
    ) -> list[FileObject]:
        """
        转存链接文件。

        :param files: 待转存文件
        :param target: 目标空间
        :param target_directory: 目标目录
        :return: 目标文件列表
        """
        file_list = list(files)
        self.transfer_batch_sizes.append(len(file_list))
        return [
            FileObject(
                space=target.locator,
                file_id='target-file-1',
                name=file.name,
                path=f'/{file.name}',
            )
            for file in file_list
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


class FakeBatchLimitedLinkSpace(FakeLinkSpace):
    """限制单次转存数量的链接文件空间。"""

    async def transfer_to(
        self,
        files: Iterable[FileObject],
        target: WritableFileSpace,
        target_directory: FileObject | None = None,
    ) -> list[FileObject]:
        """
        模拟网盘单次转存数量限制。

        :param files: 待转存文件
        :param target: 目标空间
        :param target_directory: 目标目录
        :return:
        """
        file_list = list(files)
        self.transfer_batch_sizes.append(len(file_list))
        if len(file_list) > 5:
            raise TransferBatchLimitError('单次转存文件个数超出用户等级限制')
        return [
            FileObject(
                space=target.locator,
                file_id=f'target-{file.file_id}',
                name=file.name,
                path=f'/{file.name}',
            )
            for file in file_list
        ]


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


def test_transfer_files_chunks_share_link_requests_by_ten() -> None:
    """转存文件超过 10 个时应分批提交。"""
    source = FakeLinkSpace()
    target = FakePersonalSpace()
    source_files = [
        FileObject(
            space=source.locator,
            file_id=f'source-file-{index}',
            name=f'course-{index}.pdf',
            path=f'/course-{index}.pdf',
        )
        for index in range(12)
    ]

    transferred_files = asyncio.run(transfer_files(source, source_files, target))

    assert source.transfer_batch_sizes == [10, 2]
    assert len(transferred_files) == 12


def test_transfer_files_retries_smaller_batches_when_provider_limit_is_lower_than_ten() -> None:
    """平台限制低于 10 个时应继续拆小当前批次。"""
    source = FakeBatchLimitedLinkSpace()
    target = FakePersonalSpace()
    source_files = [
        FileObject(
            space=source.locator,
            file_id=f'source-file-{index}',
            name=f'course-{index}.pdf',
            path=f'/course-{index}.pdf',
        )
        for index in range(12)
    ]

    transferred_files = asyncio.run(transfer_files(source, source_files, target))

    assert source.transfer_batch_sizes == [10, 5, 5, 2]
    assert len(transferred_files) == 12


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
