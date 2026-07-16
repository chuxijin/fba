#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.app.mydrive.service.filesystem.models import FileObject, SpaceLocator, SpaceType
from backend.app.mydrive.service.sync.planner import build_directory_sync_plan, build_post_copy_rename_plan
from backend.app.mydrive.service.sync.rules import SyncRule


SPACE = SpaceLocator(provider='baidu', space_type=SpaceType.PERSONAL)


def _file(file_id: str, name: str, size: int, is_directory: bool = False) -> FileObject:
    """
    构建测试文件对象。

    :param file_id: 文件 ID
    :param name: 文件名称
    :param size: 文件大小
    :param is_directory: 是否目录
    :return:
    """
    return FileObject(space=SPACE, file_id=file_id, name=name, path=f'/{name}', size=size, is_directory=is_directory)


def test_incremental_skips_same_name_same_size_file() -> None:
    """增量同步应跳过同名同大小文件。"""
    plan = build_directory_sync_plan([_file('source', 'same.txt', 3)], [_file('target', 'same.txt', 3)], 'incremental', [])

    assert plan.skipped_count == 1
    assert plan.files_to_copy == []
    assert plan.target_items_to_remove == []


def test_incremental_copies_changed_same_name_file() -> None:
    """增量同步应复制同名不同大小文件。"""
    source = _file('source', 'same.txt', 5)
    plan = build_directory_sync_plan([source], [_file('target', 'same.txt', 3)], 'incremental', [])

    assert plan.files_to_copy == [source]


def test_full_removes_unprocessed_target_item() -> None:
    """完全同步应删除目标多余项。"""
    plan = build_directory_sync_plan(
        [_file('source', 'same.txt', 3)],
        [_file('target-same', 'same.txt', 3), _file('target-extra', 'extra.txt', 1)],
        'full',
        [],
    )

    assert [item.file_id for item in plan.target_items_to_remove] == ['target-extra']


def test_renamed_target_is_skipped_regardless_of_size() -> None:
    """命中重命名结果的文件应按旧同步语义跳过。"""
    plan = build_directory_sync_plan(
        [_file('source', '原名.txt', 8)],
        [_file('target', '新名.txt', 5)],
        'incremental',
        [SyncRule('rename', '原名', '新名')],
    )

    assert plan.skipped_count == 1
    assert plan.files_to_copy == []


def test_renamed_target_directory_is_skipped() -> None:
    """命中重命名结果的目标目录应按 CouldDrive 语义跳过。"""
    plan = build_directory_sync_plan(
        [_file('source', '原名.txt', 8)],
        [_file('target', '新名.txt', 0, is_directory=True)],
        'incremental',
        [SyncRule('rename', '原名', '新名')],
    )

    assert plan.skipped_count == 1
    assert plan.files_to_copy == []


def test_post_copy_rename_only_handles_copied_files() -> None:
    """重命名计划只处理本次复制成功的文件。"""
    file = _file('target', '原名.txt', 1)

    assert build_post_copy_rename_plan([file], [SyncRule('rename', '原名', '新名')]) == [(file, '新名.txt')]
