#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

from backend.app.coulddrive.service.rule_template_service import MatchTarget
from backend.app.coulddrive.service.rule_template_service import RenameRule
from backend.app.coulddrive.service.utils_service import build_full_path
from backend.app.coulddrive.service.utils_service import join_path


@dataclass(slots=True)
class FolderSyncPlan:
    """目录同步计划"""

    source_name: str
    source_path: str
    target_path: str
    target_file_id: str | None
    target_exists: bool


@dataclass(slots=True)
class DirectorySyncPlan:
    """单目录同步计划"""

    folders: list[FolderSyncPlan] = field(default_factory=list)
    files_to_transfer: list[dict[str, Any]] = field(default_factory=list)
    processed_target_signatures: set[tuple[str, int]] = field(default_factory=set)
    files_processed: int = 0
    files_skipped: int = 0


def build_transfer_file_info(
    file_name: str,
    file_size: int,
    file_info: dict[str, Any],
    source_path: str,
    target_path: str,
) -> dict[str, Any]:
    """
    构建待转存文件信息

    :param file_name: 文件名
    :param file_size: 文件大小
    :param file_info: 源文件信息
    :param source_path: 源目录路径
    :param target_path: 目标目录路径
    :return:
    """
    transfer_file_info = {
        'file_name': file_name,
        'file_size': file_size,
        'source_path': source_path,
        'target_path': target_path,
        'file_id': file_info.get('file_id', ''),
    }

    transfer_file_info.update({key: value for key, value in file_info.items() if key not in ['file_size', 'file_id']})

    return transfer_file_info


def build_directory_sync_plan(
    source_file_map: dict[str, dict[str, Any]],
    target_file_map: dict[str, dict[str, Any]],
    source_path: str,
    target_path: str,
    rename_rules: list[RenameRule] | None = None,
) -> DirectorySyncPlan:
    """
    构建单目录同步计划

    :param source_file_map: 源文件映射
    :param target_file_map: 目标文件映射
    :param source_path: 源目录路径
    :param target_path: 目标目录路径
    :param rename_rules: 重命名规则
    :return:
    """
    plan = DirectorySyncPlan()

    for source_filename, source_file_info in source_file_map.items():
        if source_filename.endswith('/'):
            plan.folders.append(
                _build_folder_sync_plan(source_filename, target_file_map, source_path, target_path)
            )
            continue

        _append_file_sync_action(
            plan,
            source_filename,
            source_file_info,
            source_path,
            target_path,
            target_file_map,
            rename_rules,
        )

    return plan


def build_target_delete_plan(
    target_file_map: dict[str, dict[str, Any]],
    processed_target_signatures: set[tuple[str, int]],
    target_path: str,
) -> list[dict[str, Any]]:
    """
    构建目标多余项删除计划

    :param target_file_map: 目标文件映射
    :param processed_target_signatures: 已处理目标文件签名集合
    :param target_path: 目标目录路径
    :return:
    """
    files_to_delete: list[dict[str, Any]] = []

    for target_filename, target_file_info in target_file_map.items():
        target_is_folder = target_filename.endswith('/')
        target_size = target_file_info.get('file_size', 0) if not target_is_folder else 0
        target_signature = (target_filename, target_size)

        if target_signature in processed_target_signatures:
            continue

        files_to_delete.append({
            'file_name': target_filename,
            'file_size': target_size,
            'target_path': target_path,
            'file_id': target_file_info.get('file_id', ''),
        })

    return files_to_delete


def _build_folder_sync_plan(
    source_filename: str,
    target_file_map: dict[str, dict[str, Any]],
    source_path: str,
    target_path: str,
) -> FolderSyncPlan:
    """
    构建子目录同步计划

    :param source_filename: 源目录名
    :param target_file_map: 目标文件映射
    :param source_path: 源目录路径
    :param target_path: 目标目录路径
    :return:
    """
    dir_name = source_filename.rstrip('/')
    target_file_info = target_file_map.get(source_filename)

    return FolderSyncPlan(
        source_name=source_filename,
        source_path=join_path(source_path, dir_name, is_dir=True),
        target_path=join_path(target_path, dir_name, is_dir=True),
        target_file_id=target_file_info.get('file_id', '') if target_file_info else None,
        target_exists=source_filename in target_file_map,
    )

def _append_file_sync_action(
    plan: DirectorySyncPlan,
    source_filename: str,
    source_file_info: dict[str, Any],
    source_path: str,
    target_path: str,
    target_file_map: dict[str, dict[str, Any]],
    rename_rules: list[RenameRule] | None,
) -> None:
    """
    追加文件同步动作

    :param plan: 当前目录同步计划
    :param source_filename: 源文件名
    :param source_file_info: 源文件信息
    :param source_path: 源目录路径
    :param target_path: 目标目录路径
    :param target_file_map: 目标文件映射
    :param rename_rules: 重命名规则
    :return:
    """
    plan.files_processed += 1
    source_size = source_file_info.get('file_size', 0)
    target_file_info = target_file_map.get(source_filename)

    if target_file_info and not target_file_info.get('is_folder', False):
        _append_same_name_file_action(
            plan,
            source_filename,
            source_size,
            source_file_info,
            source_path,
            target_path,
            target_file_info,
        )
        return

    if _mark_rule_renamed_target_as_processed(
        plan,
        source_filename,
        source_path,
        target_path,
        target_file_map,
        rename_rules,
    ):
        return

    plan.files_to_transfer.append(
        build_transfer_file_info(source_filename, source_size, source_file_info, source_path, target_path)
    )


def _append_same_name_file_action(
    plan: DirectorySyncPlan,
    source_filename: str,
    source_size: int,
    source_file_info: dict[str, Any],
    source_path: str,
    target_path: str,
    target_file_info: dict[str, Any],
) -> None:
    """
    追加同名文件同步动作

    :param plan: 当前目录同步计划
    :param source_filename: 源文件名
    :param source_size: 源文件大小
    :param source_file_info: 源文件信息
    :param source_path: 源目录路径
    :param target_path: 目标目录路径
    :param target_file_info: 目标文件信息
    :return:
    """
    target_size = target_file_info.get('file_size', -1)
    if source_size == target_size:
        plan.files_skipped += 1
        plan.processed_target_signatures.add((source_filename, source_size))
    else:
        plan.files_to_transfer.append(
            build_transfer_file_info(source_filename, source_size, source_file_info, source_path, target_path)
        )
        plan.processed_target_signatures.add((source_filename, target_size))

def _mark_rule_renamed_target_as_processed(
    plan: DirectorySyncPlan,
    source_filename: str,
    source_path: str,
    target_path: str,
    target_file_map: dict[str, dict[str, Any]],
    rename_rules: list[RenameRule] | None,
) -> bool:
    """
    标记命中重命名规则的目标文件已处理

    :param plan: 当前目录同步计划
    :param source_filename: 源文件名
    :param source_path: 源目录路径
    :param target_path: 目标目录路径
    :param target_file_map: 目标文件映射
    :param rename_rules: 重命名规则
    :return:
    """
    if not rename_rules:
        return False

    source_full_path = build_full_path(source_path, source_filename)
    temp_item = SimpleNamespace(file_name=source_filename, file_path=source_full_path)

    for rule in rename_rules:
        generated_value = rule.generate_new_path(temp_item)
        if not generated_value:
            continue

        renamed_target_name = source_filename
        renamed_target_path = source_full_path
        if rule.target_scope == MatchTarget.NAME:
            renamed_target_name = generated_value
            renamed_target_path = build_full_path(target_path, renamed_target_name)
        elif rule.target_scope == MatchTarget.PATH:
            renamed_target_path = generated_value
            renamed_target_name = renamed_target_path.rstrip('/').split('/')[-1]

        target_file_info = target_file_map.get(renamed_target_name)
        if not target_file_info:
            continue

        target_signature = (renamed_target_name, target_file_info.get('file_size', 0))
        if target_signature in plan.processed_target_signatures:
            continue

        plan.files_skipped += 1
        plan.processed_target_signatures.add(target_signature)
        return True

    return False
