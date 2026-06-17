#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""错题掌握状态相关定时任务"""

import logging

from sqlalchemy import select

from backend.app.question_bank.model.mastery import WrongMasteryStatus
from backend.app.task.celery import celery_app
from backend.database.db import async_db_session
from backend.utils.timezone import timezone

logger = logging.getLogger(__name__)


@celery_app.task(name='check_forgotten_mastery')
async def check_forgotten_mastery() -> dict:
    """
    检查并标记遗忘的题目（每天凌晨 3:00 执行）

    将 status='mastered' 且 next_review_time < now() 的记录标记为 status='forgotten'
    """
    try:
        result = await _check_forgotten_mastery()
        logger.info(f'遗忘检测完成: 共标记 {result["total_forgotten"]} 个题目为遗忘状态')
        return result
    except Exception as e:
        logger.error(f'遗忘检测失败: {str(e)}')
        return {'total_forgotten': 0, 'error': str(e)}


async def _check_forgotten_mastery() -> dict:
    """遗忘检测的异步实现"""
    async with async_db_session.begin() as db:
        now = timezone.now()

        # 查询所有需要标记为遗忘的记录
        stmt = select(WrongMasteryStatus).where(
            WrongMasteryStatus.status == 'mastered',
            WrongMasteryStatus.next_review_time < now,
            WrongMasteryStatus.deleted == 0,
        )
        result = await db.execute(stmt)
        forgotten_records = result.scalars().all()

        total_forgotten = len(forgotten_records)

        # 批量更新状态
        for record in forgotten_records:
            record.status = 'forgotten'

        await db.commit()

        return {
            'total_forgotten': total_forgotten,
            'check_time': str(now),
        }
