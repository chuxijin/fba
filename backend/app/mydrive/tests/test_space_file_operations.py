#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio

import pytest

from backend.app.mydrive.schema.file import MyDriveFileReference
from backend.app.mydrive.service.filesystem.models import FileObject, SpaceLocator, SpaceType
from backend.app.mydrive.service.filesystem.spaces import FileSpace, WritableFileSpace
from backend.app.mydrive.service.space_service import MyDriveSpaceService
from backend.common.exception import errors


class FakeWritableSpace(WritableFileSpace):
    """可写文件空间替身。"""

    def __init__(self) -> None:
        """初始化可写文件空间替身。"""
        self._locator = SpaceLocator(provider='quark', space_type=SpaceType.PERSONAL, account_id='1')
        self.created_name: str | None = None
        self.closed = False

    @property
    def locator(self) -> SpaceLocator:
        """获取文件空间定位信息。"""
        return self._locator

    async def aclose(self) -> None:
        """标记资源已关闭。"""
        self.closed = True

    async def list(self, directory: FileObject | None = None) -> list[FileObject]:
        """返回空文件列表。"""
        return []

    async def get(self, file_id: str) -> FileObject | None:
        """不返回文件对象。"""
        return None

    async def make_directory(self, name: str, parent: FileObject | None = None) -> FileObject:
        """创建替身目录。"""
        self.created_name = name
        return FileObject(space=self.locator, file_id='directory-1', name=name, path=f'/{name}', is_directory=True)

    async def copy(self, files: list[FileObject], target: FileObject | None = None) -> None:
        """忽略复制操作。"""

    async def move(self, files: list[FileObject], target: FileObject | None = None) -> None:
        """忽略移动操作。"""

    async def rename(self, file: FileObject, new_name: str) -> FileObject:
        """返回重命名文件。"""
        return FileObject(space=self.locator, file_id=file.file_id, name=new_name, path=f'/{new_name}')

    async def remove(self, files: list[FileObject]) -> None:
        """忽略删除操作。"""


class FakeReadOnlySpace(FileSpace):
    """只读文件空间替身。"""

    def __init__(self) -> None:
        """初始化只读文件空间替身。"""
        self._locator = SpaceLocator(provider='quark', space_type=SpaceType.SHARE_LINK, account_id='1')
        self.closed = False

    @property
    def locator(self) -> SpaceLocator:
        """获取文件空间定位信息。"""
        return self._locator

    async def aclose(self) -> None:
        """标记资源已关闭。"""
        self.closed = True

    async def list(self, directory: FileObject | None = None) -> list[FileObject]:
        """返回空文件列表。"""
        return []

    async def get(self, file_id: str) -> FileObject | None:
        """不返回文件对象。"""
        return None


def test_make_directory_uses_writable_space_and_closes_resource(monkeypatch: pytest.MonkeyPatch) -> None:
    """创建目录应委派可写空间并关闭资源。"""
    file_space = FakeWritableSpace()

    async def get_space(db: object, *, pk: int, owner_id: int) -> object:
        """返回空间占位对象。"""
        return object()

    async def create_space(db: object, space: object) -> FakeWritableSpace:
        """返回可写空间替身。"""
        return file_space

    monkeypatch.setattr(MyDriveSpaceService, 'get', get_space)
    monkeypatch.setattr('backend.app.mydrive.service.space_service.create_file_space', create_space)

    directory = asyncio.run(
        MyDriveSpaceService.make_directory(
            object(),
            pk=1,
            owner_id=2,
            name='courses',
            parent=None,
        )
    )

    assert directory.name == 'courses'
    assert file_space.created_name == 'courses'
    assert file_space.closed is True


def test_copy_files_rejects_read_only_space_and_closes_resource(monkeypatch: pytest.MonkeyPatch) -> None:
    """复制文件应拒绝只读空间并关闭资源。"""
    file_space = FakeReadOnlySpace()

    async def get_space(db: object, *, pk: int, owner_id: int) -> object:
        """返回空间占位对象。"""
        return object()

    async def create_space(db: object, space: object) -> FakeReadOnlySpace:
        """返回只读空间替身。"""
        return file_space

    monkeypatch.setattr(MyDriveSpaceService, 'get', get_space)
    monkeypatch.setattr('backend.app.mydrive.service.space_service.create_file_space', create_space)

    file = MyDriveFileReference(file_id='file-1', name='course.pdf', path='/course.pdf')
    with pytest.raises(errors.ForbiddenError, match='不支持写入'):
        asyncio.run(MyDriveSpaceService.copy_files(object(), pk=1, owner_id=2, files=[file]))

    assert file_space.closed is True
