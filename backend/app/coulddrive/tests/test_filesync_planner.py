#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from backend.app.coulddrive.service.filesync.planner import build_directory_sync_plan, build_target_delete_plan
from backend.app.coulddrive.service.rule_template_service import RenameRule


def test_build_directory_sync_plan_copies_new_file_and_tracks_missing_folder() -> None:
    """新文件和缺失目录应进入同步计划"""
    source_file_map = {
        'new.txt': {'file_size': 7, 'file_id': 'source-file-id', 'sign': 'source-sign'},
        'course/': {'file_id': 'source-dir-id', 'is_folder': True},
    }
    target_file_map = {}

    plan = build_directory_sync_plan(source_file_map, target_file_map, '/source', '/target')

    assert plan.files_processed == 1
    assert plan.files_skipped == 0
    assert plan.files_to_transfer == [
        {
            'file_name': 'new.txt',
            'file_size': 7,
            'source_path': '/source',
            'target_path': '/target',
            'file_id': 'source-file-id',
            'sign': 'source-sign',
        }
    ]
    assert len(plan.folders) == 1
    assert plan.folders[0].source_name == 'course/'
    assert plan.folders[0].source_path == '/source/course/'
    assert plan.folders[0].target_path == '/target/course/'
    assert plan.folders[0].target_exists is False


def test_build_directory_sync_plan_skips_same_file() -> None:
    """同名同大小文件应跳过"""
    source_file_map = {'same.txt': {'file_size': 3, 'file_id': 'source-file-id'}}
    target_file_map = {'same.txt': {'file_size': 3, 'file_id': 'target-file-id'}}

    plan = build_directory_sync_plan(source_file_map, target_file_map, '/source', '/target')

    assert plan.files_processed == 1
    assert plan.files_skipped == 1
    assert plan.files_to_transfer == []
    assert plan.processed_target_signatures == {('same.txt', 3)}


def test_build_directory_sync_plan_copies_changed_same_name_file() -> None:
    """同名不同大小文件应复制覆盖"""
    source_file_map = {'same.txt': {'file_size': 5, 'file_id': 'source-file-id'}}
    target_file_map = {'same.txt': {'file_size': 3, 'file_id': 'target-file-id'}}

    plan = build_directory_sync_plan(source_file_map, target_file_map, '/source', '/target')

    assert plan.files_processed == 1
    assert plan.files_skipped == 0
    assert plan.files_to_transfer[0]['file_name'] == 'same.txt'
    assert plan.files_to_transfer[0]['file_size'] == 5
    assert plan.processed_target_signatures == {('same.txt', 3)}


def test_build_directory_sync_plan_treats_same_size_different_name_as_new_file() -> None:
    """不同名文件即便同大小也应视为新文件"""
    source_file_map = {'new.txt': {'file_size': 5, 'file_id': 'source-file-id'}}
    target_file_map = {'old.txt': {'file_size': 5, 'file_id': 'target-file-id'}}

    plan = build_directory_sync_plan(source_file_map, target_file_map, '/source', '/target')

    assert plan.files_processed == 1
    assert plan.files_skipped == 0
    assert plan.files_to_transfer == [
        {
            'file_name': 'new.txt',
            'file_size': 5,
            'source_path': '/source',
            'target_path': '/target',
            'file_id': 'source-file-id',
        }
    ]
    assert plan.processed_target_signatures == set()


def test_build_directory_sync_plan_skips_rule_renamed_same_size_file() -> None:
    """命中重命名规则且目标已改名时应跳过"""
    source_file_map = {'1 再来一杯柠檬水.txt': {'file_size': 5, 'file_id': 'source-file-id'}}
    target_file_map = {'1 有岸上.txt': {'file_size': 5, 'file_id': 'target-file-id'}}
    rename_rules = [RenameRule(match_regex='再来一杯柠檬水', replace_string='有岸上')]

    plan = build_directory_sync_plan(source_file_map, target_file_map, '/source', '/target', rename_rules=rename_rules)

    assert plan.files_processed == 1
    assert plan.files_skipped == 1
    assert plan.files_to_transfer == []
    assert plan.processed_target_signatures == {('1 有岸上.txt', 5)}


def test_build_directory_sync_plan_skips_rule_renamed_changed_size_file() -> None:
    """命中重命名规则时即便大小变化也不应重复保存"""
    source_file_map = {'1 再来一杯柠檬水.txt': {'file_size': 8, 'file_id': 'source-file-id'}}
    target_file_map = {'1 有岸上.txt': {'file_size': 5, 'file_id': 'target-file-id'}}
    rename_rules = [RenameRule(match_regex='再来一杯柠檬水', replace_string='有岸上')]

    plan = build_directory_sync_plan(source_file_map, target_file_map, '/source', '/target', rename_rules=rename_rules)

    assert plan.files_processed == 1
    assert plan.files_skipped == 1
    assert plan.files_to_transfer == []
    assert plan.processed_target_signatures == {('1 有岸上.txt', 5)}


def test_build_directory_sync_plan_tracks_existing_folder() -> None:
    """已存在目录应记录目标目录 ID"""
    source_file_map = {'course/': {'file_id': 'source-dir-id', 'is_folder': True}}
    target_file_map = {'course/': {'file_id': 'target-dir-id', 'is_folder': True}}

    plan = build_directory_sync_plan(source_file_map, target_file_map, '/source', '/target')

    assert len(plan.folders) == 1
    assert plan.folders[0].target_exists is True
    assert plan.folders[0].target_file_id == 'target-dir-id'
    assert plan.files_processed == 0


def test_build_target_delete_plan_collects_unprocessed_target_items() -> None:
    """未处理目标项应进入 full 删除计划"""
    target_file_map = {
        'same.txt': {'file_size': 3, 'file_id': 'same-id'},
        'extra.txt': {'file_size': 5, 'file_id': 'extra-id'},
        'extra_dir/': {'file_size': 99, 'file_id': 'extra-dir-id'},
    }
    processed_target_signatures = {('same.txt', 3)}

    delete_plan = build_target_delete_plan(target_file_map, processed_target_signatures, '/target')

    assert delete_plan == [
        {
            'file_name': 'extra.txt',
            'file_size': 5,
            'target_path': '/target',
            'file_id': 'extra-id',
        },
        {
            'file_name': 'extra_dir/',
            'file_size': 0,
            'target_path': '/target',
            'file_id': 'extra-dir-id',
        },
    ]
