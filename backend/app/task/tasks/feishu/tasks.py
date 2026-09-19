#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from backend.app.mydrive.crud.crud_feishu import feishu_sheet_config_dao
from backend.app.mydrive.service.feishu_export_service import mydrive_feishu_export_service
from backend.app.task.celery import celery_app
from backend.database.db import async_db_session
from backend.utils.timezone import timezone


class FeishuExportTaskExecutionError(Exception):
    """飞书表导出任务执行失败。"""


@celery_app.task(name='feishu:execute_export_task')
async def execute_feishu_export_task(task_id: int) -> dict[str, Any]:
    """
    执行飞书表导出任务。

    :param task_id: 导出任务 ID
    :return:
    """
    async with async_db_session.begin() as db:
        # begin() 已经托管事务，交给它统一提交；这里再 commit 会提前关闭事务
        result = await mydrive_feishu_export_service.execute_task(db, task_id, commit=False)

    if not result.get('success'):
        raise FeishuExportTaskExecutionError(_build_failure_message(result))

    return _compact_success_result(result)


@celery_app.task(name='feishu:check_and_execute_cron_tasks')
async def check_and_execute_feishu_cron_tasks() -> dict[str, Any]:
    """检查并派发飞书表定时导出任务。"""
    result: dict[str, Any] = {'checked': 0, 'dispatched': 0, 'skipped': 0, 'failed': 0, 'details': []}
    current_time = timezone.now()

    async with async_db_session() as db:
        configs = await feishu_sheet_config_dao.list_enabled_cron_configs(db)
        result['checked'] = len(configs)
        for config in configs:
            try:
                if config.end_time is not None and current_time > config.end_time:
                    result['skipped'] += 1
                    result['details'].append({'config_id': config.id, 'status': 'skipped', 'reason': '配置已过期'})
                    continue
                if not mydrive_feishu_export_service.should_execute_now(
                    config.cron or '', config.last_synced_at, current_time
                ):
                    result['skipped'] += 1
                    result['details'].append({'config_id': config.id, 'status': 'skipped', 'reason': '未到执行时间'})
                    continue
                task = await mydrive_feishu_export_service.create_task(db, config_id=config.id)
                await db.commit()
                await db.refresh(task)
                execute_feishu_export_task.delay(task.id)
                result['dispatched'] += 1
                result['details'].append({'config_id': config.id, 'task_id': task.id, 'status': 'dispatched'})
            except Exception as exc:
                await db.rollback()
                result['failed'] += 1
                result['details'].append({'config_id': config.id, 'status': 'failed', 'reason': str(exc)})

    return _compact_success_result(result)


@celery_app.task(name='feishu:init_sheet')
async def init_feishu_sheet(config_id: int) -> dict[str, Any]:
    """
    初始化指定配置的飞书表格（重命名 / 表头 / 样式 / 下拉）。

    :param config_id: 导出配置 ID
    :return:
    """
    async with async_db_session() as db:
        config = await mydrive_feishu_export_service.get_config(db, pk=config_id)

    return await mydrive_feishu_export_service.init_all(config)


def _compact_success_result(result: dict[str, Any]) -> dict[str, Any]:
    """
    压缩 Celery 成功日志中的返回结果。

    :param result: 原始任务结果
    :return:
    """
    return {key: value for key, value in result.items() if key not in {'details', 'items', 'records'}}


def _build_failure_message(result: dict[str, Any]) -> str:
    """
    构建飞书表导出失败信息。

    :param result: 导出执行结果
    :return:
    """
    config_name = str(result.get('config_name') or '').strip()
    config_part = f'（{config_name}）' if config_name else ' '
    return f'飞书表导出任务 {result.get("task_id")}{config_part}执行失败: {result.get("error") or "未知错误"}'
