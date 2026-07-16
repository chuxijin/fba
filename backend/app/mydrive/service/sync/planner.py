#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from dataclasses import dataclass, field

from backend.app.mydrive.service.filesystem.models import FileObject
from backend.app.mydrive.service.sync.rules import SyncRule, rename_name


@dataclass(slots=True)
class DirectorySyncPlan:
    """单目录同步计划"""

    directories_to_create: list[FileObject] = field(default_factory=list)
    files_to_copy: list[FileObject] = field(default_factory=list)
    files_to_rename: list[tuple[FileObject, str]] = field(default_factory=list)
    target_items_to_remove: list[FileObject] = field(default_factory=list)
    skipped_count: int = 0


def build_directory_sync_plan(
    source_items: list[FileObject],
    target_items: list[FileObject],
    sync_method: str,
    rules: list[SyncRule],
) -> DirectorySyncPlan:
    """
    按 CouldDrive 语义构建单目录同步计划。

    :param source_items: 源目录项目
    :param target_items: 目标目录项目
    :param sync_method: 同步模式
    :param rules: 同步规则
    :return:
    """
    plan = DirectorySyncPlan()
    target_by_name = {item.name: item for item in target_items}
    processed_target_ids: set[str] = set()

    for source_item in source_items:
        target_item = target_by_name.get(source_item.name)
        if source_item.is_directory:
            _plan_directory(plan, source_item, target_item, processed_target_ids)
            continue
        _plan_file(plan, source_item, target_item, target_by_name, processed_target_ids, rules)

    if sync_method == 'full':
        plan.target_items_to_remove = [item for item in target_items if item.file_id not in processed_target_ids]
    return plan


def _plan_directory(
    plan: DirectorySyncPlan,
    source_item: FileObject,
    target_item: FileObject | None,
    processed_target_ids: set[str],
) -> None:
    """规划目录处理。"""
    if target_item is None:
        plan.directories_to_create.append(source_item)
        return
    if target_item.is_directory:
        processed_target_ids.add(target_item.file_id)
        return
    plan.target_items_to_remove.append(target_item)
    plan.directories_to_create.append(source_item)
    processed_target_ids.add(target_item.file_id)


def _plan_file(
    plan: DirectorySyncPlan,
    source_item: FileObject,
    target_item: FileObject | None,
    target_by_name: dict[str, FileObject],
    processed_target_ids: set[str],
    rules: list[SyncRule],
) -> None:
    """规划文件处理。"""
    if target_item is not None and not target_item.is_directory:
        processed_target_ids.add(target_item.file_id)
        if source_item.size == target_item.size:
            plan.skipped_count += 1
            return
        plan.files_to_copy.append(source_item)
        return

    renamed_target = target_by_name.get(rename_name(source_item.name, rules))
    if renamed_target is not None:
        processed_target_ids.add(renamed_target.file_id)
        plan.skipped_count += 1
        return
    if target_item is not None:
        processed_target_ids.add(target_item.file_id)
        plan.target_items_to_remove.append(target_item)
    plan.files_to_copy.append(source_item)


def build_post_copy_rename_plan(files: list[FileObject], rules: list[SyncRule]) -> list[tuple[FileObject, str]]:
    """
    为本次复制成功的文件构建重命名计划。

    :param files: 本次成功复制的文件
    :param rules: 同步规则
    :return:
    """
    return [(file, renamed_name) for file in files if (renamed_name := rename_name(file.name, rules)) != file.name]
