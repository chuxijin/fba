#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""题库相关定时任务"""
import logging

from datetime import datetime, timedelta
from decimal import Decimal

import sqlalchemy as sa

from sqlalchemy import func, select

from backend.app.question_bank.crud.crud_daily_rank import daily_rank_dao
from backend.app.question_bank.model import PracticeRecord, UserAccount
from backend.app.task.celery import celery_app
from backend.database.db import async_db_session
from backend.utils.timezone import timezone

logger = logging.getLogger(__name__)


@celery_app.task(name='update_daily_user_ranks')
async def update_daily_user_ranks() -> dict:
    """
    更新每日用户排名（每天0:05执行）

    计算昨天的用户练习数据并生成排名
    """
    try:
        result = await _update_daily_user_ranks()
        logger.info(f"排名更新完成: 共更新 {result['total_users']} 个用户排名")
        return result
    except Exception as e:
        logger.error(f"排名更新失败: {str(e)}")
        return {'total_users': 0, 'error': str(e)}


async def _update_daily_user_ranks() -> dict:
    """更新每日用户排名的异步实现"""
    async with async_db_session() as db:
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)
        yesterday_start = datetime.combine(yesterday, datetime.min.time())
        today_start = datetime.combine(today, datetime.min.time())

        stmt = (
            select(
                UserAccount.user_id.label('user_id'),
                func.count(PracticeRecord.id).label('practice_count'),
                func.sum(func.cast(PracticeRecord.is_correct, sa.Integer)).label('correct_count'),
            )
            .outerjoin(
                PracticeRecord,
                (PracticeRecord.user_id == UserAccount.user_id)
                & (PracticeRecord.created_time >= yesterday_start)
                & (PracticeRecord.created_time < today_start),
            )
            .group_by(UserAccount.user_id)
            .order_by(func.count(PracticeRecord.id).desc())
        )

        result = await db.execute(stmt)
        user_stats = result.all()

        total_users = len(user_stats)
        created_count = 0

        for rank, row in enumerate(user_stats, 1):
            practice_count = row.practice_count or 0
            correct_count = row.correct_count or 0

            beat_percentage = (
                Decimal((total_users - rank) / total_users * 100).quantize(Decimal('0.01'))
                if total_users > 0
                else Decimal('0')
            )

            accuracy_rate = (
                Decimal((correct_count / practice_count) * 100).quantize(Decimal('0.01'))
                if practice_count > 0
                else Decimal('0')
            )

            await daily_rank_dao.create_rank_record(
                db=db,
                user_id=row.user_id,
                rank_date=yesterday,
                rank=rank,
                total_users=total_users,
                beat_percentage=beat_percentage,
                practice_count=practice_count,
                correct_count=correct_count,
                accuracy_rate=accuracy_rate,
            )
            created_count += 1

        await db.commit()

        return {
            'total_users': total_users,
            'created_ranks': created_count,
            'rank_date': str(yesterday),
        }


@celery_app.task(name='simulate_bot_activity')
async def simulate_bot_activity() -> dict:
    """
    模拟机器人每日活动（每天凌晨 2:00 执行）

    自动创建新机器人用户并模拟已有机器人的刷题行为
    """
    from backend.app.question_bank.service.bot_service import run_bot_simulation

    try:
        result = await run_bot_simulation()
        logger.info(f'机器人模拟完成: {result}')
        return result
    except Exception as e:
        logger.error(f'机器人模拟失败: {str(e)}')
        return {'error': str(e)}
