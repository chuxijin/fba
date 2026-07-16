#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
from typing import Any

from backend.app.mydrive.service.drives.baidu.personal_space import BaiduPersonalSpace
from backend.app.mydrive.service.drives.baidu.relationship_space import BaiduRelationshipSpace
from backend.app.mydrive.service.filesystem.models import SpaceType


class FakeBaiduRelationshipRequest:
    """百度关系分享请求替身。"""

    def __init__(self) -> None:
        """初始化关系分享请求替身。"""
        self.transfer_data: dict[str, Any] | None = None

    async def list_relationship_share_files(self, **kwargs: Any) -> list[dict[str, Any]]:
        """返回关系分享目录内容。"""
        assert kwargs['space_type'] == 'friend'
        assert kwargs['source_id'] == 'friend-1'
        assert kwargs['from_uk'] == 'friend-1'
        assert kwargs['message_id'] == 'message-1'
        assert kwargs['file_id'] == 'root-1'
        return [{'fs_id': 'file-1', 'path': '/course.pdf', 'server_filename': 'course.pdf', 'isdir': 0, 'size': 1_024}]

    async def transfer_relationship_files(self, **kwargs: Any) -> None:
        """记录关系分享转存请求。"""
        self.transfer_data = kwargs

    async def list_files(self, path: str) -> list[dict[str, Any]]:
        """返回目标个人目录内容。"""
        assert path == '/'
        return [{'fs_id': 'target-1', 'path': '/course.pdf', 'server_filename': 'course.pdf', 'isdir': 0, 'size': 1_024}]

    async def aclose(self) -> None:
        """关闭替身。"""


def test_baidu_friend_space_browses_and_transfers_to_personal_space() -> None:
    """百度好友分享空间应浏览并原生转存。"""
    client = FakeBaiduRelationshipRequest()
    source = BaiduRelationshipSpace(
        account_id=1,
        cookie='cookie',
        space_type=SpaceType.FRIEND,
        source_id='friend-1',
        from_uk='friend-1',
        message_id='message-1',
        root_id='root-1',
        client=client,
    )
    target = BaiduPersonalSpace(account_id=1, cookie='cookie', client=client)

    files = asyncio.run(source.list())
    transferred_files = asyncio.run(source.transfer_to(files, target))

    assert files[0].name == 'course.pdf'
    assert client.transfer_data is not None
    assert client.transfer_data['file_ids'] == ['file-1']
    assert client.transfer_data['target_path'] == '/'
    assert [file.file_id for file in transferred_files] == ['target-1']
