#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
from typing import Any

from backend.app.mydrive.service.drives.quark.personal_space import QuarkPersonalSpace
from backend.app.mydrive.service.drives.quark.share_space import QuarkShareSpace


class FakeQuarkShareRequest:
    """夸克分享请求替身。"""

    def __init__(self) -> None:
        """初始化夸克分享请求替身。"""
        self.saved_data: dict[str, Any] | None = None

    async def get_share_token(self, share_id: str, passcode: str = '') -> str:
        """
        返回分享访问令牌。

        :param share_id: 分享标识
        :param passcode: 分享提取码
        :return:
        """
        assert share_id == 'share-1'
        assert passcode == 'code'
        return 'share-token'

    async def list_share_files(self, share_id: str, token: str, parent_id: str = '0') -> list[dict[str, Any]]:
        """
        返回分享文件列表。

        :param share_id: 分享标识
        :param token: 分享访问令牌
        :param parent_id: 父目录 ID
        :return:
        """
        assert share_id == 'share-1'
        assert token == 'share-token'
        assert parent_id == '0'
        return [
            {
                'fid': 'shared-file-1',
                'file_name': 'course.pdf',
                'pdir_fid': '0',
                'dir': False,
                'size': 1_024,
                'share_fid_token': 'file-token-1',
            }
        ]

    async def save_share_files(
        self,
        share_id: str,
        token: str,
        parent_id: str,
        file_ids: list[str],
        file_tokens: list[str],
        target_id: str,
    ) -> None:
        """
        记录分享转存请求。

        :param share_id: 分享标识
        :param token: 分享访问令牌
        :param parent_id: 分享父目录 ID
        :param file_ids: 分享文件 ID 列表
        :param file_tokens: 分享文件访问令牌列表
        :param target_id: 目标目录 ID
        :return:
        """
        self.saved_data = {
            'share_id': share_id,
            'token': token,
            'parent_id': parent_id,
            'file_ids': file_ids,
            'file_tokens': file_tokens,
            'target_id': target_id,
        }

    async def list_files(self, parent_id: str) -> list[dict[str, Any]]:
        """
        返回目标目录文件。

        :param parent_id: 父目录 ID
        :return:
        """
        assert parent_id == '0'
        return [{'fid': 'target-file-1', 'file_name': 'course.pdf', 'pdir_fid': '0', 'dir': False, 'size': 1_024}]


def test_quark_share_space_browses_and_transfers_to_personal_space() -> None:
    """夸克分享空间应作为只读挂载浏览并单向转存。"""
    client = FakeQuarkShareRequest()
    source = QuarkShareSpace(account_id=1, cookie='cookie', share_id='share-1', passcode='code', client=client)
    target = QuarkPersonalSpace(account_id=1, cookie='cookie', client=client)

    files = asyncio.run(source.list())
    transferred_files = asyncio.run(source.transfer_to(files, target))

    assert files[0].path == '/course.pdf'
    assert files[0].extra['share_file_token'] == 'file-token-1'
    assert client.saved_data == {
        'share_id': 'share-1',
        'token': 'share-token',
        'parent_id': '0',
        'file_ids': ['shared-file-1'],
        'file_tokens': ['file-token-1'],
        'target_id': '0',
    }
    assert [file.file_id for file in transferred_files] == ['target-file-1']
