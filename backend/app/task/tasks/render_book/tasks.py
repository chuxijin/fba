#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging

from datetime import timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from backend.app.task.celery import celery_app
from backend.core.conf import settings
from backend.database.db import async_db_session
from backend.plugin.render_book.crud import render_book_job_dao
from backend.plugin.render_book.model import RenderBookJob
from backend.utils.timezone import timezone

logger = logging.getLogger(__name__)

EXPIRE_DAYS = 90
BATCH_SIZE = 200


def _as_string_list(value: object) -> list[str]:
    """
    转换字符串列表

    :param value: 原始值
    :return:
    """
    if not isinstance(value, list):
        return []

    return [item for item in value if isinstance(item, str) and item.strip()]


def _normalize_oss_path(value: str | None) -> str:
    """
    规范化 OSS 路径片段

    :param value: 原始路径
    :return:
    """
    if not value:
        return ''

    normalized = value.replace('\\', '/').strip('/')
    if not normalized:
        return ''
    return '/'.join(part for part in normalized.split('/') if part and part != '.')


def _build_render_book_oss_path(job_id: str) -> str:
    """
    构建题本 OSS 目录

    :param job_id: 外部任务 ID
    :return:
    """
    prefix = _normalize_oss_path(getattr(settings, 'RENDER_BOOK_OSS_PATH_PREFIX', 'render-book'))
    if not prefix:
        return job_id
    return f'{prefix}/{job_id}'


def _infer_preview_object_key(job_id: str, preview_url: str) -> str | None:
    """
    从旧版预览图 URL 回推 OSS 对象 Key

    :param job_id: 外部任务 ID
    :param preview_url: 预览图 URL
    :return:
    """
    parsed = urlparse(preview_url)
    if parsed.scheme not in {'http', 'https'}:
        return None

    object_path = _normalize_oss_path(parsed.path)
    if not object_path:
        return None

    render_path = _build_render_book_oss_path(job_id)
    storage_prefix = _normalize_oss_path(getattr(settings, 'STORAGE_KEY_PREFIX', ''))
    candidates = []
    if storage_prefix:
        candidates.append(f'{storage_prefix}/{render_path}')
    candidates.append(render_path)

    for marker in candidates:
        index = object_path.find(marker)
        if index >= 0:
            return object_path[index:]

    return None


async def _delete_oss_object(object_key: str) -> bool:
    """
    删除单个 OSS 对象，失败时记录 warning 但不抛出

    :param object_key: OSS 对象 Key
    :return:
    """
    try:
        from backend.plugin.oss.service.storage_service import storage_service
    except Exception as exc:
        logger.warning(f'OSS 插件不可用，跳过远端删除 object_key={object_key}: {exc!r}')
        return False

    try:
        async with async_db_session() as db:
            return await storage_service.delete_object(db=db, object_key=object_key)
    except Exception as exc:
        logger.warning(f'删除 OSS 对象失败 object_key={object_key}: [{type(exc).__name__}] {exc!r}')
        return False


def _delete_local_file(local_path: str) -> bool:
    """
    删除单个本地文件，失败时记录 warning 但不抛出

    :param local_path: 本地文件路径
    :return:
    """
    try:
        path = Path(local_path)
        if path.exists() and path.is_file():
            path.unlink()
        return True
    except Exception as exc:
        logger.warning(f'删除本地文件失败 local_path={local_path}: [{type(exc).__name__}] {exc!r}')
        return False


def _collect_preview_object_keys(job: RenderBookJob) -> list[str]:
    """
    收集预览图 OSS 对象 Key

    :param job: 题本任务实例
    :return:
    """
    metadata = job.metadata_json or {}
    object_keys = _as_string_list(metadata.get('preview_object_keys'))
    legacy_urls = _as_string_list(metadata.get('preview_urls'))
    for preview_url in legacy_urls:
        object_key = _infer_preview_object_key(job.job_id, preview_url)
        if object_key:
            object_keys.append(object_key)

    return list(dict.fromkeys(object_keys))


def _collect_preview_local_paths(job: RenderBookJob) -> list[str]:
    """
    收集预览图本地路径

    :param job: 题本任务实例
    :return:
    """
    metadata = job.metadata_json or {}
    local_paths = _as_string_list(metadata.get('preview_local_paths'))
    legacy_urls = _as_string_list(metadata.get('preview_urls'))
    for preview_url in legacy_urls:
        parsed = urlparse(preview_url)
        if parsed.scheme:
            continue
        local_paths.append(preview_url)

    return list(dict.fromkeys(local_paths))


async def _purge_job_files(job: RenderBookJob) -> dict[str, int]:
    """
    清理单个任务关联的所有 OSS 对象与本地文件

    :param job: 题本任务实例（需附带 files 关系）
    :return:
    """
    stats = {'oss_deleted': 0, 'oss_failed': 0, 'local_deleted': 0, 'local_failed': 0}
    object_keys: list[str] = []
    local_paths: list[str] = []
    for file_record in job.files or []:
        if file_record.object_key:
            object_keys.append(file_record.object_key)
        if file_record.local_path:
            local_paths.append(file_record.local_path)

    object_keys.extend(_collect_preview_object_keys(job))
    local_paths.extend(_collect_preview_local_paths(job))

    for object_key in dict.fromkeys(object_keys):
        if await _delete_oss_object(object_key):
            stats['oss_deleted'] += 1
        else:
            stats['oss_failed'] += 1

    for local_path in dict.fromkeys(local_paths):
        if _delete_local_file(local_path):
            stats['local_deleted'] += 1
        else:
            stats['local_failed'] += 1

    return stats


@celery_app.task(name='render_book:cleanup_expired_render_books')
async def cleanup_expired_render_books() -> dict[str, Any]:
    """清理 90 天以前的题本任务（OSS 对象 + 本地文件 + 数据库记录）"""
    threshold = timezone.now() - timedelta(days=EXPIRE_DAYS)
    summary: dict[str, Any] = {
        'success': True,
        'threshold': threshold.isoformat(),
        'scanned_jobs': 0,
        'deleted_jobs': 0,
        'oss_deleted': 0,
        'oss_failed': 0,
        'local_deleted': 0,
        'local_failed': 0,
        'errors': [],
    }

    try:
        while True:
            async with async_db_session() as db:
                jobs = await render_book_job_dao.list_expired_jobs(
                    db=db,
                    threshold=threshold,
                    limit=BATCH_SIZE,
                )
                if not jobs:
                    break

                summary['scanned_jobs'] += len(jobs)
                for job in jobs:
                    try:
                        file_stats = await _purge_job_files(job)
                        summary['oss_deleted'] += file_stats['oss_deleted']
                        summary['oss_failed'] += file_stats['oss_failed']
                        summary['local_deleted'] += file_stats['local_deleted']
                        summary['local_failed'] += file_stats['local_failed']

                        # DB 记录无条件删除（按需求：能删就删，失败仅记 log）
                        deleted = await render_book_job_dao.hard_delete_by_id(db, job_pk=job.id)
                        if deleted:
                            summary['deleted_jobs'] += 1
                    except Exception as exc:
                        msg = f'清理题本任务失败 job_id={job.job_id}: [{type(exc).__name__}] {exc!r}'
                        logger.warning(msg)
                        summary['errors'].append(msg)

                await db.commit()

                if len(jobs) < BATCH_SIZE:
                    break

        logger.info(
            f'[cleanup_expired_render_books] '
            f'threshold={summary["threshold"]} '
            f'scanned={summary["scanned_jobs"]} deleted_jobs={summary["deleted_jobs"]} '
            f'oss_deleted={summary["oss_deleted"]} oss_failed={summary["oss_failed"]} '
            f'local_deleted={summary["local_deleted"]} local_failed={summary["local_failed"]}'
        )
    except Exception as exc:
        summary['success'] = False
        summary['error'] = f'[{type(exc).__name__}] {exc!r}'
        logger.error(f'清理过期题本任务整体失败: {summary["error"]}')

    return {
        'success': summary['success'],
        'threshold': summary['threshold'],
        'scanned_jobs': summary['scanned_jobs'],
        'deleted_jobs': summary['deleted_jobs'],
        'oss_deleted': summary['oss_deleted'],
        'oss_failed': summary['oss_failed'],
        'local_deleted': summary['local_deleted'],
        'local_failed': summary['local_failed'],
        'error_count': len(summary['errors']),
        **({'error': summary['error']} if 'error' in summary else {}),
    }
