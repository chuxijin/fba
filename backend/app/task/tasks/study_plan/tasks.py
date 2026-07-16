#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""学习规划相关定时任务"""

import logging

from backend.app.study_plan.crud import study_plan_item_dao
from backend.app.task.celery import celery_app
from backend.database.db import async_db_session
from backend.utils.timezone import timezone

logger = logging.getLogger(__name__)


@celery_app.task(name='study_plan:sweep_expired_study_plan_items')
async def sweep_expired_study_plan_items() -> dict:
    """
    扫描所有学员的过期未完成计划项并标记为 skipped（每天 0:30 执行）

    实现 D13 跨天处理：今日之前的 pending/in_progress 全部归入历史
    """
    try:
        result = await _sweep_expired_study_plan_items()
        logger.info(f'学习规划过期项清理完成: 标记 {result["skipped"]} 项为 skipped')
        return result
    except Exception as e:
        logger.error(f'学习规划过期项清理失败: {e}')
        return {'skipped': 0, 'error': str(e)}


async def _sweep_expired_study_plan_items() -> dict:
    """扫描并标记过期计划项的异步实现"""
    today = timezone.now().date()
    async with async_db_session.begin() as db:
        affected = await study_plan_item_dao.bulk_skip_pending_before(db, today)
    return {'skipped': affected, 'before_date': today.isoformat()}
