#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
from typing import Any

from backend.app.mydrive.service.drives.quark.personal_space import QuarkPersonalSpace


class FakeQuarkRequest:
    """夸克请求替身。"""

    def __init__(self) -> None:
        """初始化夸克请求替身。"""
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
        assert parent_id == '0'
        return [
            {
                'fid': 'file-1',
                'file_name': 'course.pdf',
                'pdir_fid': '0',
                'dir': False,
                'size': 1_024,
                'created_at': 1_700_000_000_000,
                'updated_at': 1_700_000_100_000,
                'md5': 'hash-1',
            }
        ]

    async def make_directory(self, parent_id: str, name: str) -> dict[str, Any]:
        """
        返回新目录。

        :param parent_id: 父目录 ID
        :param name: 目录名称
        :return:
        """
        return {'fid': 'folder-1', 'file_name': name, 'pdir_fid': parent_id, 'dir': True, 'size': 0}

    async def copy_files(self, file_ids: list[str], target_id: str) -> None:
        """
        记录复制请求。

        :param file_ids: 文件 ID 列表
        :param target_id: 目标目录 ID
        :return:
        """
        self.copied_file_ids = file_ids
        self.copy_target_id = target_id

    async def rename_file(self, file_id: str, new_name: str) -> None:
        """
        记录重命名请求。

        :param file_id: 文件 ID
        :param new_name: 新名称
        :return:
        """
        self.renamed_file = (file_id, new_name)

    async def move_files(self, file_ids: list[str], target_id: str) -> None:
        """
        记录移动请求。

        :param file_ids: 文件 ID 列表
        :param target_id: 目标目录 ID
        :return:
        """
        self.moved_file_ids = file_ids
        self.move_target_id = target_id

    async def remove_files(self, file_ids: list[str]) -> None:
        """
        记录删除请求。

        :param file_ids: 文件 ID 列表
        :return:
        """
        self.removed_file_ids = file_ids

    async def search_files(self, keyword: str) -> list[dict[str, Any]]:
        """
        返回搜索结果。

        :param keyword: 搜索关键词
        :return:
        """
        assert keyword == '四海'
        return [{
            'fid': 'search-1',
            'file_name': '【四海】讲义.pdf',
            'pdir_fid': 'parent-1',
            'file_type': 1,
            'size': 100,
            'thumbnail': 'https://thumbnail',
            'hl_file_name': '【<hl>四海</hl>】讲义.pdf',
            'format_type': 'application/pdf',
            'obj_category': 'doc',
            'source_display': 'save_share',
        }]


def test_quark_personal_space_maps_file_and_delegates_operations() -> None:
    """夸克个人空间应统一文件对象并委派写操作。"""
    client = FakeQuarkRequest()
    space = QuarkPersonalSpace(account_id=1, cookie='cookie', client=client)

    files = asyncio.run(space.list())

    assert files[0].file_id == 'file-1'
    assert files[0].path == '/course.pdf'
    assert files[0].size == 1_024
    assert asyncio.run(space.get('file-1')) == files[0]

    directory = asyncio.run(space.make_directory('courses'))
    asyncio.run(space.copy(files, directory))
    asyncio.run(space.move(files, directory))
    renamed_file = asyncio.run(space.rename(files[0], 'renamed.pdf'))
    asyncio.run(space.remove([files[0]]))

    assert directory.file_id == 'folder-1'
    assert client.copied_file_ids == ['file-1']
    assert client.copy_target_id == 'folder-1'
    assert client.moved_file_ids == ['file-1']
    assert client.move_target_id == 'folder-1'
    assert client.renamed_file == ('file-1', 'renamed.pdf')
    assert renamed_file.path == '/renamed.pdf'
    assert client.removed_file_ids == ['file-1']
    assert asyncio.run(space.get('file-1')) is None


def test_quark_personal_space_searches_files() -> None:
    """夸克个人空间应统一搜索结果。"""
    space = QuarkPersonalSpace(account_id=1, cookie='cookie', client=FakeQuarkRequest())

    files = asyncio.run(space.search('四海'))

    assert files[0].file_id == 'search-1'
    assert files[0].name == '【四海】讲义.pdf'
    assert files[0].parent_id == 'parent-1'
    assert files[0].extra['highlight_name'] == '【<hl>四海</hl>】讲义.pdf'
    assert files[0].extra['obj_category'] == 'doc'
