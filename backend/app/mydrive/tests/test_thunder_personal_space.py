#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
from typing import Any

from backend.app.mydrive.service.drives.thunder.personal_space import ThunderPersonalSpace


class FakeThunderRequest:
    """迅雷个人盘请求替身。"""

    def __init__(self) -> None:
        """初始化迅雷个人盘请求替身。"""
        self.copied_file_ids: list[str] = []
        self.copy_target_id: str | None = None
        self.moved_file_ids: list[str] = []
        self.move_target_id: str | None = None
        self.renamed_file: tuple[str, str] | None = None
        self.removed_file_ids: list[str] = []

    async def list_files(self, parent_id: str) -> list[dict[str, Any]]:
        """
        返回目录文件列表。

        :param parent_id: 父目录 ID
        :return:
        """
        assert parent_id == ''
        return [{'id': 'file-1', 'parent_id': '', 'name': 'course.pdf', 'kind': 'drive#file', 'size': '1024'}]

    async def make_directory(self, parent_id: str, name: str) -> dict[str, Any]:
        """
        返回新目录。

        :param parent_id: 父目录 ID
        :param name: 目录名称
        :return:
        """
        return {'id': 'folder-1', 'parent_id': parent_id, 'name': name, 'kind': 'drive#folder', 'size': '0'}

    async def copy_files(self, file_ids: list[str], target_id: str) -> None:
        """
        记录复制请求。

        :param file_ids: 文件 ID 列表
        :param target_id: 目标目录 ID
        :return:
        """
        self.copied_file_ids = file_ids
        self.copy_target_id = target_id

    async def move_files(self, file_ids: list[str], target_id: str) -> None:
        """
        记录移动请求。

        :param file_ids: 文件 ID 列表
        :param target_id: 目标目录 ID
        :return:
        """
        self.moved_file_ids = file_ids
        self.move_target_id = target_id

    async def rename_file(self, file_id: str, name: str) -> None:
        """
        记录重命名请求。

        :param file_id: 文件 ID
        :param name: 新名称
        :return:
        """
        self.renamed_file = (file_id, name)

    async def remove_files(self, file_ids: list[str]) -> None:
        """
        记录删除请求。

        :param file_ids: 文件 ID 列表
        :return:
        """
        self.removed_file_ids = file_ids

    async def aclose(self) -> None:
        """关闭请求替身。"""


def test_thunder_personal_space_maps_files_and_delegates_operations() -> None:
    """迅雷个人空间应统一文件对象并委派写操作。"""
    client = FakeThunderRequest()
    space = ThunderPersonalSpace(account_id=1, credential={'refresh_token': 'token'}, client=client)

    files = asyncio.run(space.list())
    directory = asyncio.run(space.make_directory('courses'))
    asyncio.run(space.copy(files, directory))
    asyncio.run(space.move(files, directory))
    renamed_file = asyncio.run(space.rename(files[0], 'renamed.pdf'))
    asyncio.run(space.remove(files))

    assert files[0].file_id == 'file-1'
    assert files[0].size == 1_024
    assert directory.file_id == 'folder-1'
    assert client.copied_file_ids == ['file-1']
    assert client.copy_target_id == 'folder-1'
    assert client.moved_file_ids == ['file-1']
    assert client.move_target_id == 'folder-1'
    assert client.renamed_file == ('file-1', 'renamed.pdf')
    assert renamed_file.path == '/renamed.pdf'
    assert client.removed_file_ids == ['file-1']
