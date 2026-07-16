#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
from typing import Any

from backend.app.mydrive.service.drives.baidu.client import BaiduRequestError
from backend.app.mydrive.service.drives.baidu.personal_space import BaiduPersonalSpace
from backend.app.mydrive.service.filesystem.models import FileObject


class FakeBaiduPersonalRequest:
    """百度个人盘请求替身。"""

    def __init__(self) -> None:
        """初始化百度个人盘请求替身。"""
        self.copied_paths: list[str] = []
        self.copy_target_path: str | None = None
        self.moved_paths: list[str] = []
        self.move_target_path: str | None = None
        self.renamed_file: tuple[str, str] | None = None
        self.removed_paths: list[str] = []

    async def list_files(self, path: str) -> list[dict[str, Any]]:
        """
        返回目录文件列表。

        :param path: 目录路径
        :return:
        """
        assert path == '/'
        return [{'fs_id': 1, 'path': '/course.pdf', 'server_filename': 'course.pdf', 'isdir': 0, 'size': 1_024}]

    async def make_directory(self, path: str) -> dict[str, Any]:
        """
        返回新目录。

        :param path: 目录路径
        :return:
        """
        return {'fs_id': 2, 'path': path, 'server_filename': 'courses', 'isdir': 1, 'size': 0}

    async def copy_files(self, paths: list[str], target_path: str) -> None:
        """
        记录复制请求。

        :param paths: 源路径列表
        :param target_path: 目标目录路径
        :return:
        """
        self.copied_paths = paths
        self.copy_target_path = target_path

    async def move_files(self, paths: list[str], target_path: str) -> None:
        """
        记录移动请求。

        :param paths: 源路径列表
        :param target_path: 目标目录路径
        :return:
        """
        self.moved_paths = paths
        self.move_target_path = target_path

    async def rename_file(self, path: str, new_path: str) -> None:
        """
        记录重命名请求。

        :param path: 原路径
        :param new_path: 新路径
        :return:
        """
        self.renamed_file = (path, new_path)

    async def remove_files(self, paths: list[str]) -> None:
        """
        记录删除请求。

        :param paths: 文件路径列表
        :return:
        """
        self.removed_paths = paths

    async def aclose(self) -> None:
        """关闭请求替身。"""


def test_baidu_personal_space_maps_files_and_delegates_operations() -> None:
    """百度个人空间应统一文件对象并委派写操作。"""
    client = FakeBaiduPersonalRequest()
    space = BaiduPersonalSpace(account_id=1, cookie='cookie', client=client)

    files = asyncio.run(space.list())
    directory = asyncio.run(space.make_directory('courses'))
    asyncio.run(space.copy(files, directory))
    asyncio.run(space.move(files, directory))
    renamed_file = asyncio.run(space.rename(files[0], 'renamed.pdf'))
    asyncio.run(space.remove(files))

    assert files[0].file_id == '1'
    assert directory.path == '/courses'
    assert client.copied_paths == ['/course.pdf']
    assert client.copy_target_path == '/courses'
    assert client.moved_paths == ['/course.pdf']
    assert client.move_target_path == '/courses'
    assert client.renamed_file == ('/course.pdf', '/renamed.pdf')
    assert renamed_file.path == '/renamed.pdf'
    assert client.removed_paths == ['/course.pdf']


def test_baidu_personal_space_recovers_stale_root_path_by_root_id() -> None:
    """百度个人空间应通过根目录 ID 恢复已变更的根路径。"""

    class StaleRootClient:
        """根路径已变更的百度个人盘替身。"""

        def __init__(self) -> None:
            """初始化根路径记录。"""
            self.paths: list[str] = []

        async def list_files(self, path: str) -> list[dict[str, Any]]:
            """
            按路径返回目录内容。

            :param path: 目录路径
            :return:
            """
            self.paths.append(path)
            if path == '/旧目录':
                raise BaiduRequestError('百度网盘请求失败，错误码：-9', error_code=-9)
            return [{'fs_id': 2, 'path': '/新目录/course.pdf', 'server_filename': 'course.pdf', 'isdir': 0}]

        async def get_file_metadata(self, file_id: str) -> dict[str, Any] | None:
            """
            返回根目录当前元数据。

            :param file_id: 文件 ID
            :return:
            """
            assert file_id == 'root-1'
            return {'fs_id': file_id, 'isdir': 1, 'path': '/新目录'}

        async def aclose(self) -> None:
            """关闭替身客户端。"""

    client = StaleRootClient()
    space = BaiduPersonalSpace(account_id=1, cookie='cookie', root_id='root-1', root_path='/旧目录', client=client)

    files = asyncio.run(space.list())

    assert client.paths == ['/旧目录', '/新目录']
    assert files[0].path == '/新目录/course.pdf'
    assert space.locator.root_path == '/新目录'


def test_baidu_personal_space_searches_files() -> None:
    """百度个人空间应委派搜索请求。"""

    class SearchClient(FakeBaiduPersonalRequest):
        """记录搜索请求。"""

        def __init__(self) -> None:
            """初始化搜索记录。"""
            super().__init__()
            self.search_args: tuple[str, str, bool] | None = None

        async def search_files(self, keyword: str, path: str, recursive: bool = False) -> list[dict[str, Any]]:
            """返回搜索结果。"""
            self.search_args = (keyword, path, recursive)
            return [{'fs_id': 3, 'path': '/课程/course.pdf', 'server_filename': 'course.pdf', 'isdir': 0, 'size': 2}]

    client = SearchClient()
    space = BaiduPersonalSpace(account_id=1, cookie='cookie', client=client)

    files = asyncio.run(space.search('course', '/课程', True))

    assert client.search_args == ('course', '/课程', True)
    assert files[0].path == '/课程/course.pdf'


def test_baidu_personal_space_uses_provider_directory_path() -> None:
    """百度个人空间应直接使用通用层转换后的驱动目录路径。"""

    class SubdirectoryClient:
        """记录百度目录读取路径的替身。"""

        def __init__(self) -> None:
            """初始化路径记录。"""
            self.paths: list[str] = []

        async def list_files(self, path: str) -> list[dict[str, Any]]:
            """
            记录目录读取路径。

            :param path: 目录路径
            :return:
            """
            self.paths.append(path)
            return []

        async def aclose(self) -> None:
            """关闭替身客户端。"""

    client = SubdirectoryClient()
    space = BaiduPersonalSpace(account_id=1, cookie='cookie', root_path='/【02】公考类', client=client)
    directory = FileObject(
        space=space.locator,
        file_id='50245458827233',
        name='【01】国考省考',
        path='/【02】公考类/【01】国考省考',
        is_directory=True,
    )

    asyncio.run(space.list(directory))

    assert client.paths == ['/【02】公考类/【01】国考省考']
