#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from croniter import croniter

from backend.app.mydrive.crud.crud_sync import mydrive_sync_config_dao
from backend.app.mydrive.service.sync.executor import mydrive_sync_executor
from backend.app.mydrive.service.sync_service import mydrive_sync_service
from backend.app.task.celery import celery_app
from backend.database.db import async_db_session
from backend.utils.timezone import timezone

MYDRIVE_CRON_WINDOW_MINUTES = 5


@celery_app.task(name='mydrive:execute_sync_task')
async def execute_mydrive_sync_task(task_id: int) -> dict[str, Any]:
    """
    执行 MyDrive 同步任务。

    :param task_id: 同步任务 ID
    :return:
    """
    async with async_db_session.begin() as db:
        result = await mydrive_sync_executor.execute(db, task_id)
        return _compact_success_result(result)


@celery_app.task(name='mydrive:check_and_execute_cron_tasks')
async def check_and_execute_mydrive_cron_tasks() -> dict[str, Any]:
    """检查并派发 MyDrive 定时同步任务。"""
    result: dict[str, Any] = {'checked': 0, 'dispatched': 0, 'skipped': 0, 'failed': 0, 'details': []}
    current_time = timezone.now()

    async with async_db_session() as db:
        configs = await mydrive_sync_config_dao.list_enabled_cron_configs(db)
        result['checked'] = len(configs)
        for config in configs:
            try:
                if config.end_time is not None and current_time > config.end_time:
                    result['skipped'] += 1
                    result['details'].append({'config_id': config.id, 'status': 'skipped', 'reason': '配置已过期'})
                    continue
                if not _should_execute_now(config.cron or '', config.last_synced_at, current_time):
                    result['skipped'] += 1
                    result['details'].append({'config_id': config.id, 'status': 'skipped', 'reason': '未到执行时间'})
                    continue
                task = await mydrive_sync_service.create_task(db, config_id=config.id, owner_id=config.owner_id)
                await db.commit()
                await db.refresh(task)
                execute_mydrive_sync_task.delay(task.id)
                result['dispatched'] += 1
                result['details'].append({'config_id': config.id, 'task_id': task.id, 'status': 'dispatched'})
            except Exception as exc:
                await db.rollback()
                result['failed'] += 1
                result['details'].append({'config_id': config.id, 'status': 'failed', 'reason': str(exc)})

    return _compact_success_result(result)


@celery_app.task(name='mydrive:process_resource_temp_policies')
async def process_mydrive_resource_temp_policies() -> dict[str, Any]:
    """处理 MyDrive 资源临时策略。"""
    async with async_db_session.begin() as db:
        from backend.app.mydrive.service.resource_service import mydrive_resource_service

        result = await mydrive_resource_service.process_temp_policy_resources(db)
        return _compact_success_result(result)


@celery_app.task(name='mydrive:process_expired_resource_policies')
async def process_mydrive_expired_resource_policies() -> dict[str, Any]:
    """处理 MyDrive 到期资源策略。"""
    async with async_db_session.begin() as db:
        from backend.app.mydrive.service.resource_service import mydrive_resource_service

        result = await mydrive_resource_service.process_expired_resource_policies(db)
        return _compact_success_result(result)


@celery_app.task(name='mydrive:refresh_scheduled_resource_shares')
async def refresh_mydrive_scheduled_resource_shares() -> dict[str, Any]:
    """刷新 MyDrive 定时更新资源的分享信息。"""
    async with async_db_session.begin() as db:
        from backend.app.mydrive.service.resource_service import mydrive_resource_service

        result = await mydrive_resource_service.refresh_scheduled_resource_shares(db)
        return _compact_success_result(result)


@celery_app.task(name='mydrive:cleanup_expired_local_shares')
async def cleanup_mydrive_expired_local_shares() -> dict[str, Any]:
    """清理 MyDrive 账户的本地过期分享。"""
    async with async_db_session.begin() as db:
        from backend.app.mydrive.service.share_cleanup_service import mydrive_share_cleanup_service

        result = await mydrive_share_cleanup_service.cleanup_expired_local_shares(db)
        return _compact_success_result(result)


@celery_app.task(name='mydrive:sync_active_account_profiles')
async def sync_mydrive_active_account_profiles() -> dict[str, object]:
    """同步 MyDrive 活跃账户资料。"""
    async with async_db_session.begin() as db:
        from backend.app.mydrive.service.account_service import mydrive_account_service

        result = await mydrive_account_service.sync_active_profiles(db)
        return _compact_success_result(result)


def _compact_success_result(result: dict[str, Any]) -> dict[str, Any]:
    """
    压缩 Celery 成功日志中的返回结果。

    :param result: 原始任务结果
    :return:
    """
    return {
        key: value
        for key, value in result.items()
        if key not in {'details', 'items', 'records'}
    }


def _should_execute_now(cron_expr: str, last_synced_at: datetime | None, current_time: datetime) -> bool:
    """
    判断当前检查窗口是否应执行。

    :param cron_expr: Cron 表达式
    :param last_synced_at: 最近同步时间
    :param current_time: 当前时间
    :return:
    """
    if not cron_expr.strip():
        return False
    cron = croniter(cron_expr, current_time)
    previous_time = cron.get_prev(datetime)
    diff_minutes = (current_time - previous_time).total_seconds() / 60
    if diff_minutes < 0 or diff_minutes > MYDRIVE_CRON_WINDOW_MINUTES:
        return False
    if last_synced_at is None:
        return True
    return last_synced_at < previous_time
