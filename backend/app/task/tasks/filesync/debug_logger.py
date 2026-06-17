#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import logging
import os

from typing import Any

from backend.core.path_conf import LOG_DIR
from backend.utils.timezone import timezone

# 临时调试日志文件路径
DEBUG_LOG_DIR = LOG_DIR / 'filesync_debug'
DEBUG_LOG_DIR.mkdir(parents=True, exist_ok=True)

# 每次运行生成独立文件，方便区分
_debug_logger: logging.Logger | None = None


def get_debug_logger() -> logging.Logger:
    """获取调试日志实例（单例）"""
    global _debug_logger
    if _debug_logger is not None:
        return _debug_logger

    _debug_logger = logging.getLogger('filesync_debug')
    _debug_logger.setLevel(logging.DEBUG)
    _debug_logger.propagate = False  # 不传播到根 logger

    # 按日期命名，每天一个文件
    today = timezone.now().strftime('%Y-%m-%d')
    log_file = DEBUG_LOG_DIR / f'filesync_debug_{today}.log'

    handler = logging.FileHandler(str(log_file), encoding='utf-8')
    handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter('%(asctime)s | %(levelname)-7s | %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    _debug_logger.addHandler(handler)

    return _debug_logger


def log_task_dispatch(task_name: str, config_id: int, celery_task_id: str) -> None:
    """
    记录任务派发

    :param task_name: 任务名称
    :param config_id: 配置 ID
    :param celery_task_id: Celery 任务 ID
    :return:
    """
    dl = get_debug_logger()
    dl.info(
        f'{"=" * 60}\n'
        f'  [派发] task={task_name}, config_id={config_id}\n'
        f'  celery_task_id={celery_task_id}\n'
        f'  时间={timezone.now().isoformat()}\n'
        f'{"=" * 60}'
    )


def log_task_start(config_id: int, task_id: int | None, celery_task_id: str | None = None) -> None:
    """
    记录任务开始执行

    :param config_id: 配置 ID
    :param task_id: 数据库任务 ID
    :param celery_task_id: Celery 任务 ID
    :return:
    """
    dl = get_debug_logger()
    dl.info(f'[开始] config_id={config_id}, db_task_id={task_id}, celery_task_id={celery_task_id}, pid={os.getpid()}')


def log_task_skipped(config_id: int, reason: str) -> None:
    """
    记录任务被跳过

    :param config_id: 配置 ID
    :param reason: 跳过原因
    :return:
    """
    dl = get_debug_logger()
    dl.warning(f'[跳过] config_id={config_id}, 原因: {reason}')


def log_overwrite_scan(
    task_id: int | None, phase: str, path: str, file_count: int, file_names: list[str] | None = None
) -> None:
    """
    记录覆盖同步的目录扫描结果

    :param task_id: 任务 ID
    :param phase: 阶段（source_scan / target_scan_before_delete / target_scan_after_transfer）
    :param path: 扫描路径
    :param file_count: 文件数量
    :param file_names: 文件名列表
    :return:
    """
    dl = get_debug_logger()
    names_str = ''
    if file_names:
        names_str = '\n    '.join(file_names[:50])
        if len(file_names) > 50:
            names_str += f'\n    ... 还有 {len(file_names) - 50} 个'
    dl.info(
        f'[扫描] task_id={task_id}, 阶段={phase}\n  路径: {path}\n  数量: {file_count}\n  文件列表:\n    {names_str}'
    )


def log_api_call(
    task_id: int | None, operation: str, file_count: int, api_result: Any, extra: dict[str, Any] | None = None
) -> None:
    """
    记录网盘 API 调用结果

    :param task_id: 任务 ID
    :param operation: 操作类型（delete / transfer）
    :param file_count: 文件数量
    :param api_result: API 返回值
    :param extra: 额外信息
    :return:
    """
    dl = get_debug_logger()
    extra_str = ''
    if extra:
        try:
            extra_str = f'\n  额外信息: {json.dumps(extra, ensure_ascii=False, default=str)[:500]}'
        except Exception:
            extra_str = f'\n  额外信息: {str(extra)[:500]}'
    dl.info(
        f'[API] task_id={task_id}, 操作={operation}, 文件数={file_count}\n'
        f'  API返回: {api_result} (类型: {type(api_result).__name__}){extra_str}'
    )


def log_target_verify(
    task_id: int | None, target_path: str, expected_count: int, actual_count: int, actual_files: list[str] | None = None
) -> None:
    """
    记录转存后的目标目录验证

    :param task_id: 任务 ID
    :param target_path: 目标路径
    :param expected_count: 预期文件数
    :param actual_count: 实际文件数
    :param actual_files: 实际文件列表
    :return:
    """
    dl = get_debug_logger()
    match_status = '✅ 一致' if actual_count >= expected_count else '❌ 不一致！'
    names_str = ''
    if actual_files:
        names_str = '\n    '.join(actual_files[:50])
        if len(actual_files) > 50:
            names_str += f'\n    ... 还有 {len(actual_files) - 50} 个'

    dl.info(
        f'[验证] task_id={task_id}, 目标路径: {target_path}\n'
        f'  预期文件数: {expected_count}\n'
        f'  实际文件数: {actual_count}\n'
        f'  状态: {match_status}\n'
        f'  实际文件:\n    {names_str}'
    )


def log_task_end(
    config_id: int, task_id: int | None, success: bool, stats: dict[str, Any] | None = None, error: str | None = None
) -> None:
    """
    记录任务结束

    :param config_id: 配置 ID
    :param task_id: 任务 ID
    :param success: 是否成功
    :param stats: 统计信息
    :param error: 错误信息
    :return:
    """
    dl = get_debug_logger()
    stats_str = ''
    if stats:
        safe_stats = {k: v for k, v in stats.items() if k not in ('pending_task_items', 'transferred_files_info')}
        try:
            stats_str = json.dumps(safe_stats, ensure_ascii=False, default=str)
        except Exception:
            stats_str = str(safe_stats)

    status = '✅ 成功' if success else '❌ 失败'
    dl.info(
        f'[结束] config_id={config_id}, task_id={task_id}, 状态={status}\n'
        f'  统计: {stats_str}\n'
        f'  错误: {error or "无"}\n'
        f'{"=" * 60}'
    )
