#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
from typing import Any

from backend.app.mydrive.service.drives.baidu.personal_space import BaiduPersonalSpace
from backend.app.mydrive.service.drives.baidu.share_space import BaiduShareSpace


class FakeBaiduShareRequest:
    """百度分享请求替身。"""

    def __init__(self) -> None:
        """初始化百度分享请求替身。"""
        self.saved_data: dict[str, Any] | None = None

    async def get_share_root(self, url: str, passcode: str = '') -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """
        返回分享根目录。

        :param url: 分享链接
        :param passcode: 分享提取码
        :return:
        """
        assert url == 'https://pan.baidu.com/s/1share'
        assert passcode == 'code'
        context = {'uk': 1, 'share_id': 2, 'bdstoken': 'share-token', 'url': url}
        return context, [{'fs_id': 3, 'path': '/course.pdf', 'server_filename': 'course.pdf', 'isdir': 0, 'size': 1_024}]

    async def save_share_files(self, context: dict[str, Any], file_ids: list[str], target_path: str) -> None:
        """
        记录分享转存请求。

        :param context: 分享上下文
        :param file_ids: 文件 ID 列表
        :param target_path: 目标目录路径
        :return:
        """
        self.saved_data = {'context': context, 'file_ids': file_ids, 'target_path': target_path}

    async def list_share_files(self, context: dict[str, Any], path: str) -> list[dict[str, Any]]:
        """返回分享子目录文件。"""
        assert context['uk'] == 1
        assert path == '/sharelink1/courses'
        return [{'fs_id': 3, 'path': '/course.pdf', 'server_filename': 'course.pdf', 'isdir': 0, 'size': 1_024}]

    async def list_files(self, path: str) -> list[dict[str, Any]]:
        """
        返回目标目录文件。

        :param path: 目录路径
        :return:
        """
        assert path == '/'
        return [{'fs_id': 4, 'path': '/course.pdf', 'server_filename': 'course.pdf', 'isdir': 0, 'size': 1_024}]

    async def aclose(self) -> None:
        """关闭请求替身。"""


def test_baidu_share_space_browses_and_transfers_to_personal_space() -> None:
    """百度分享空间应作为只读挂载浏览并单向转存。"""
    client = FakeBaiduShareRequest()
    source = BaiduShareSpace(
        account_id=1,
        cookie='cookie',
        url='https://pan.baidu.com/s/1share',
        passcode='code',
        client=client,
    )
    target = BaiduPersonalSpace(account_id=1, cookie='cookie', client=client)

    files = asyncio.run(source.list())
    transferred_files = asyncio.run(source.transfer_to(files, target))

    assert files[0].file_id == '3'
    assert client.saved_data is not None
    assert client.saved_data['file_ids'] == ['3']
    assert client.saved_data['target_path'] == '/'
    assert [file.file_id for file in transferred_files] == ['4']


def test_baidu_share_space_hides_provider_path_from_mounted_files() -> None:
    """百度分享空间应对外返回挂载内虚拟路径。"""

    class VirtualPathClient(FakeBaiduShareRequest):
        """返回百度分享原始目录路径的替身。"""

        async def get_share_root(self, url: str, passcode: str = '') -> tuple[dict[str, Any], list[dict[str, Any]]]:
            """
            返回分享根目录。

            :param url: 分享链接
            :param passcode: 分享提取码
            :return:
            """
            return {
                'uk': 1,
                'share_id': 2,
                'url': url,
            }, [{
                'fs_id': 3,
                'path': '/sharelink1099884833520-606499579353230/02.27牟立志数资夜生活',
                'server_filename': '02.27牟立志数资夜生活',
                'isdir': 1,
            }]

        async def list_share_files(self, context: dict[str, Any], path: str) -> list[dict[str, Any]]:
            """
            验证使用百度原始目录路径。

            :param context: 分享上下文
            :param path: 百度原始目录路径
            :return:
            """
            assert path == '/sharelink1099884833520-606499579353230/02.27牟立志数资夜生活'
            return []

    source = BaiduShareSpace(
        account_id=1,
        cookie='cookie',
        url='https://pan.baidu.com/s/1share',
        client=VirtualPathClient(),
    )

    files = asyncio.run(source.list())
    asyncio.run(source.list(files[0]))

    assert files[0].path == '/02.27牟立志数资夜生活'


def test_baidu_share_space_builds_path_from_context_and_root_id() -> None:
    """百度分享空间应忽略首项中的错误分享路径。"""

    class InvalidRootPathClient(FakeBaiduShareRequest):
        """返回含错误分享路径的分享根目录。"""

        def __init__(self) -> None:
            """初始化请求路径记录。"""
            super().__init__()
            self.paths: list[str] = []

        async def get_share_root(self, url: str, passcode: str = '') -> tuple[dict[str, Any], list[dict[str, Any]]]:
            """返回分享根目录。"""
            return {
                'uk': 1099884833520,
                'share_id': 2,
                'url': url,
            }, [{
                'fs_id': 3,
                'path': '/sharelink0-75534976739073/01.27年四海拾伊-数量基础理论课/26.第二十六节-概率问题',
                'server_filename': '26.第二十六节-概率问题',
                'isdir': 1,
            }]

        async def list_share_files(self, context: dict[str, Any], path: str) -> list[dict[str, Any]]:
            """验证使用正确的分享路径。"""
            self.paths.append(path)
            if path == '/sharelink1099884833520-75534976739073/01.27年四海拾伊-数量基础理论课':
                return [{
                    'fs_id': 4,
                    'path': '/sharelink0-75534976739073/01.27年四海拾伊-数量基础理论课/26.第二十六节-概率问题',
                    'server_filename': '26.第二十六节-概率问题',
                    'isdir': 1,
                }]
            assert path == (
                '/sharelink1099884833520-75534976739073/'
                '01.27年四海拾伊-数量基础理论课/26.第二十六节-概率问题'
            )
            return [{
                'fs_id': 4,
                'path': '/sharelink0-75534976739073/01.27年四海拾伊-数量基础理论课/26.第二十六节-概率问题/lesson.pdf',
                'server_filename': 'lesson.pdf',
                'isdir': 0,
            }]

    client = InvalidRootPathClient()
    source = BaiduShareSpace(
        account_id=1,
        cookie='cookie',
        url='https://pan.baidu.com/s/1share',
        root_id='75534976739073',
        root_path='/01.27年四海拾伊-数量基础理论课',
        client=client,
    )

    files = asyncio.run(source.list())
    nested_files = asyncio.run(source.list(files[0]))

    assert files[0].path == '/26.第二十六节-概率问题'
    assert files[0].extra['remote_path'] == (
        '/sharelink1099884833520-75534976739073/01.27年四海拾伊-数量基础理论课/26.第二十六节-概率问题'
    )
    assert nested_files[0].path == '/26.第二十六节-概率问题/lesson.pdf'
    assert client.paths == [
        '/sharelink1099884833520-75534976739073/01.27年四海拾伊-数量基础理论课',
        '/sharelink1099884833520-75534976739073/01.27年四海拾伊-数量基础理论课/26.第二十六节-概率问题',
    ]
