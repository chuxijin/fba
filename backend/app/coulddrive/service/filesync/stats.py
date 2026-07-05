#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time

from datetime import datetime
from typing import Any

from backend.utils.timezone import timezone


def create_sync_stats(sync_method: str, start_time: float) -> dict[str, Any]:
    """
    创建同步统计信息

    :param sync_method: 同步方式
    :param start_time: 开始时间戳
    :return:
    """
    return {
        'files_processed': 0,
        'folder_created': 0,
        'files_transferred': 0,
        'files_deleted': 0,
        'files_skipped': 0,
        'errors': [],
        'warnings': [],
        'local_protection_skipped': False,
        'folders_renamed': 0,
        'sync_method': sync_method,
        'start_time': datetime.fromtimestamp(start_time, tz=timezone.tz_info).isoformat(),
        'transferred_files_info': [],
        'pending_task_items': [],
    }


def finish_sync_stats(stats: dict[str, Any], start_time: float) -> None:
    """
    完成同步统计信息

    :param stats: 同步统计信息字典
    :param start_time: 开始时间戳
    :return:
    """
    stats['elapsed_time'] = time.time() - start_time
    stats['end_time'] = datetime.fromtimestamp(time.time(), tz=timezone.tz_info).isoformat()


def add_error(stats: dict[str, Any], message: str) -> None:
    """
    添加同步错误

    :param stats: 同步统计信息字典
    :param message: 错误内容
    :return:
    """
    stats.setdefault('errors', []).append(message)


def add_warning(*, stats: dict[str, Any], logger: Any, message: str) -> None:
    """
    添加同步警告

    :param stats: 同步统计信息字典
    :param logger: 日志对象
    :param message: 警告内容
    :return:
    """
    warnings = stats.setdefault('warnings', [])
    if message not in warnings:
        warnings.append(message)
    logger.warning(message)


def mark_protection_skip(*, stats: dict[str, Any], logger: Any, task_id: int | None, message: str) -> None:
    """
    标记保护性跳过

    :param stats: 同步统计信息字典
    :param logger: 日志对象
    :param task_id: 任务 ID
    :param message: 跳过原因
    :return:
    """
    full_message = f'[任务{task_id or "unknown"}] {message}'
    stats['local_protection_skipped'] = True
    add_error(stats, message)
    add_warning(stats=stats, logger=logger, message=full_message)


def is_success(stats: dict[str, Any]) -> bool:
    """
    判断同步统计是否成功

    :param stats: 同步统计信息字典
    :return:
    """
    return len(stats.get('errors', [])) == 0


def first_error(stats: dict[str, Any]) -> str | None:
    """
    获取首个同步错误

    :param stats: 同步统计信息字典
    :return:
    """
    errors = stats.get('errors', [])
    return errors[0] if errors else None


def prepare_stats_for_json(stats: dict[str, Any]) -> dict[str, Any]:
    """
    准备用于 JSON 序列化的 stats

    :param stats: 同步统计信息字典
    :return:
    """
    stats_for_json = dict(stats)
    stats_for_json.pop('pending_task_items', None)

    transferred_files = stats_for_json.get('transferred_files_info', [])
    if len(transferred_files) > 10:
        simplified = [
            {'file_name': file_info.get('file_name', ''), 'file_size': file_info.get('file_size', 0)}
            for file_info in transferred_files[:10]
        ]
        stats_for_json['transferred_files_info'] = simplified
        stats_for_json['transferred_files_count'] = len(transferred_files)

    return stats_for_json
