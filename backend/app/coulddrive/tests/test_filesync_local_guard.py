#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import asyncio

from typing import Any

import pytest

from backend.app.coulddrive.schema.file import DiskTargetDefinition, ShareSourceDefinition
from backend.app.coulddrive.service.filesync import stats as sync_stats
from backend.app.coulddrive.service.filesync.local_guard import LocalSyncGuard


class _FakeLogger:
    """测试日志收集器"""

    def __init__(self) -> None:
        """初始化测试日志收集器"""
        self.warnings: list[str] = []

    def warning(self, message: str) -> None:
        """
        记录 warning 日志

        :param message: 日志内容
        :return:
        """
        self.warnings.append(message)

    def info(self, message: str) -> None:
        """
        忽略 info 日志

        :param message: 日志内容
        :return:
        """


async def _fake_list_dir(*args, **kwargs) -> dict[str, dict[str, Any]]:
    """返回空目录列表"""
    await asyncio.sleep(0)
    return {}


async def _fake_record_task_item(*args, **kwargs) -> None:
    """忽略任务项记录"""


def _build_guard() -> LocalSyncGuard:
    """构建本地同步保护器"""
    return LocalSyncGuard(
        logger=_FakeLogger(),
        list_dir=_fake_list_dir,
        record_task_item=_fake_record_task_item,
    )


def _build_source_definition() -> ShareSourceDefinition:
    """构建本地源定义"""
    return ShareSourceDefinition(file_path='/source', source_type='local')


def _build_target_definition() -> DiskTargetDefinition:
    """构建目标定义"""
    return DiskTargetDefinition(file_path='/target', file_id='target-id')


@pytest.mark.anyio
async def test_guard_directory_changes_allows_incremental_new_files_with_target_extra_dirs() -> None:
    """增量新增文件且目标仅多目录时应放行"""
    guard = _build_guard()
    stats = sync_stats.create_sync_stats('incremental', 0)

    result = await guard.guard_directory_changes(
        service=None,
        source_definition=_build_source_definition(),
        target_definition=_build_target_definition(),
        source_path='/source',
        target_path='/target',
        target_id='target-id',
        source_file_map={
            '01.mp4': {'file_size': 1},
            '02.mp4': {'file_size': 2},
        },
        target_file_map={
            '讲义/': {'is_folder': True},
            '笔记/': {'is_folder': True},
        },
        sync_method='incremental',
        item_filter=None,
        stats=stats,
        task_id=1,
        db=None,
    )

    assert result is True
    assert stats['local_protection_skipped'] is False
    assert stats['errors'] == []
    assert len(stats['warnings']) == 1


@pytest.mark.anyio
async def test_guard_directory_changes_blocks_incremental_new_dirs_with_target_extra_dirs() -> None:
    """增量新增目录且目标有多余目录时仍应保护跳过"""
    guard = _build_guard()
    stats = sync_stats.create_sync_stats('incremental', 0)

    result = await guard.guard_directory_changes(
        service=None,
        source_definition=_build_source_definition(),
        target_definition=_build_target_definition(),
        source_path='/source',
        target_path='/target',
        target_id='target-id',
        source_file_map={
            '01.言语/': {'is_folder': True},
            '05.政治理论/': {'is_folder': True},
        },
        target_file_map={
            '言语理解/': {'is_folder': True},
            '政治理论/': {'is_folder': True},
        },
        sync_method='incremental',
        item_filter=None,
        stats=stats,
        task_id=1,
        db=None,
    )

    assert result is False
    assert stats['local_protection_skipped'] is True
    assert len(stats['errors']) == 1
    assert len(stats['warnings']) == 1
