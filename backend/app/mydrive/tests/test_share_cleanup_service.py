#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio

from datetime import timedelta

from backend.app.mydrive.service.filesystem.models import ShareLink
from backend.app.mydrive.service.share_cleanup_service import MyDriveShareCleanupService
from backend.utils.timezone import timezone


class FakeShareableFileSpace:
    """分享空间替身"""

    def __init__(self) -> None:
        self.cancelled_share_ids: list[str] = []

    async def list_shares(self, page: int, per_page: int) -> tuple[list[ShareLink], int]:
        """
        返回分享替身列表。

        :param page: 页码
        :param per_page: 每页数量
        :return:
        """
        current_time = timezone.now()
        return [
            ShareLink(provider='quark', share_id='expired', title='过期分享', url='', expired_at=current_time - timedelta(days=1)),
            ShareLink(provider='quark', share_id='active', title='有效分享', url='', expired_at=current_time + timedelta(days=1)),
            ShareLink(provider='quark', share_id='permanent', title='永久分享', url=''),
        ], 3


def test_collect_expired_share_ids_only_returns_expired_shares() -> None:
    """过期分享清理应只收集已过期的本地分享。"""
    file_space = FakeShareableFileSpace()
    share_ids = asyncio.run(MyDriveShareCleanupService._collect_expired_share_ids(file_space, timezone.now()))
    assert share_ids == ['expired']
