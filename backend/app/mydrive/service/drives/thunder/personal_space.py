#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Iterable

from backend.app.mydrive.service.filesystem.models import FileObject, SpaceLocator, SpaceType
from backend.app.mydrive.service.filesystem.spaces import WritableFileSpace
from backend.app.mydrive.service.drives.thunder.client import ThunderRequest
from backend.app.mydrive.service.drives.thunder.types import build_thunder_file


class ThunderPersonalSpace(WritableFileSpace):
    """迅雷个人文件空间。"""

    def __init__(
        self,
        account_id: int,
        credential: dict,
        root_id: str = '',
        root_path: str = '/',
        client: ThunderRequest | None = None,
    ) -> None:
        """
        初始化迅雷个人文件空间。

        :param account_id: MyDrive 账户 ID
        :param credential: 迅雷授权凭证
        :param root_id: 根目录 ID
        :param root_path: 根目录路径
        :param client: 迅雷请求封装
        """
        self._locator = SpaceLocator(
            provider='thunder',
            space_type=SpaceType.PERSONAL,
            account_id=str(account_id),
            root_id=root_id,
            root_path=root_path,
        )
        self._client = client or ThunderRequest(credential)
        self._files: dict[str, FileObject] = {}

    @property
    def locator(self) -> SpaceLocator:
        """获取迅雷个人文件空间定位信息。"""
        return self._locator

    async def aclose(self) -> None:
        """关闭迅雷个人文件空间资源。"""
        await self._client.aclose()

    async def list(self, directory: FileObject | None = None) -> list[FileObject]:
        """
        列出迅雷目录内容。

        :param directory: 待列出的目录，为空时列出空间根目录
        :return:
        """
        parent_id = directory.file_id if directory is not None else self.locator.root_id or ''
        parent_path = directory.path if directory is not None else self.locator.root_path
        files = [build_thunder_file(self.locator, item, parent_path) for item in await self._client.list_files(parent_id)]
        self._files.update({file.file_id: file for file in files})
        return files

    async def get(self, file_id: str) -> FileObject | None:
        """
        获取已读取的迅雷文件对象。

        :param file_id: 文件唯一标识
        :return:
        """
        return self._files.get(file_id)

    async def make_directory(self, name: str, parent: FileObject | None = None) -> FileObject:
        """
        创建迅雷目录。

        :param name: 目录名称
        :param parent: 父目录，为空时在空间根目录创建
        :return:
        """
        parent_id = parent.file_id if parent is not None else self.locator.root_id or ''
        parent_path = parent.path if parent is not None else self.locator.root_path
        directory = build_thunder_file(self.locator, await self._client.make_directory(parent_id, name), parent_path)
        self._files[directory.file_id] = directory
        return directory

    async def copy(self, files: Iterable[FileObject], target: FileObject | None = None) -> None:
        """
        在迅雷个人空间内复制文件。

        :param files: 待复制对象
        :param target: 目标目录，为空时使用空间根目录
        :return:
        """
        file_ids = [file.file_id for file in files]
        if file_ids:
            await self._client.copy_files(file_ids, target.file_id if target is not None else self.locator.root_id or '')

    async def move(self, files: Iterable[FileObject], target: FileObject | None = None) -> None:
        """
        在迅雷个人空间内移动文件。

        :param files: 待移动对象
        :param target: 目标目录，为空时使用空间根目录
        :return:
        """
        file_ids = [file.file_id for file in files]
        if file_ids:
            await self._client.move_files(file_ids, target.file_id if target is not None else self.locator.root_id or '')

    async def rename(self, file: FileObject, new_name: str) -> FileObject:
        """
        重命名迅雷文件或目录。

        :param file: 待重命名对象
        :param new_name: 新名称
        :return:
        """
        await self._client.rename_file(file.file_id, new_name)
        renamed_file = FileObject(
            space=file.space,
            file_id=file.file_id,
            name=new_name,
            path=f'{file.path.rsplit("/", 1)[0]}/{new_name}',
            is_directory=file.is_directory,
            size=file.size,
            parent_id=file.parent_id,
            created_at=file.created_at,
            modified_at=file.modified_at,
            hash_value=file.hash_value,
            extra=file.extra,
        )
        self._files[file.file_id] = renamed_file
        return renamed_file

    async def remove(self, files: Iterable[FileObject]) -> None:
        """
        删除迅雷文件或目录。

        :param files: 待删除对象
        :return:
        """
        file_ids = [file.file_id for file in files]
        if not file_ids:
            return
        await self._client.remove_files(file_ids)
        for file_id in file_ids:
            self._files.pop(file_id, None)
