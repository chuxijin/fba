#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""首页Dashboard服务类"""
from datetime import date, datetime, timedelta
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.model import PracticeRecord
from backend.app.question_bank.schema.home import DailyPractice, HomeDashboardData, WeekPracticeStats
from backend.app.question_bank.service.check_in_service import check_in_service
from backend.app.question_bank.service.rank_service import rank_service


class HomeService:
    """首页Dashboard服务类"""

    @staticmethod
    async def get_dashboard_data(*, db: AsyncSession, user_id: int) -> HomeDashboardData:
        """
        获取首页Dashboard数据

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        # 🔒 顺序执行查询（SQLAlchemy AsyncSession 不支持并发访问）
        check_in_info = await check_in_service.get_check_in_info(db=db, user_id=user_id)
        week_stats = await HomeService._get_week_stats(db, user_id)
        rank_info = await rank_service.get_user_rank_info(db=db, user_id=user_id)
        total_stats = await HomeService._get_total_stats(db, user_id)

        return HomeDashboardData(
            check_in=check_in_info,
            week_stats=week_stats,
            rank=rank_info,
            total_questions=total_stats['total_count'],
            total_correct=total_stats['correct_count'],
            overall_accuracy=total_stats['accuracy_rate'],
        )

    @staticmethod
    async def _get_week_stats(db: AsyncSession, user_id: int) -> WeekPracticeStats:
        """
        获取本周刷题统计

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_start_dt = datetime.combine(week_start, datetime.min.time())

        stmt = (
            select(
                func.date(PracticeRecord.created_time).label('practice_date'),
                func.count(PracticeRecord.id).label('count'),
                func.sum(func.cast(PracticeRecord.is_correct, sa.Integer)).label('correct_count'),
                func.sum(PracticeRecord.answer_time).label('duration'),
            )
            .where(
                PracticeRecord.user_id == user_id,
                PracticeRecord.created_time >= week_start_dt,
            )
            .group_by(func.date(PracticeRecord.created_time))
        )

        result = await db.execute(stmt)
        daily_data = result.all()

        daily_map = {row.practice_date: row for row in daily_data}
        daily_breakdown = []
        total_count = 0
        total_correct = 0
        total_duration = 0

        for i in range(7):
            day = week_start + timedelta(days=i)
            row = daily_map.get(day)

            if row:
                count = row.count or 0
                correct = row.correct_count or 0
                duration = row.duration or 0
            else:
                count = correct = duration = 0

            daily_breakdown.append(
                DailyPractice(
                    date=day,
                    count=count,
                    correct_count=correct,
                    duration=duration,
                )
            )

            total_count += count
            total_correct += correct
            total_duration += duration

        accuracy_rate = (
            Decimal((total_correct / total_count) * 100).quantize(Decimal('0.01'))
            if total_count > 0
            else Decimal('0')
        )

        return WeekPracticeStats(
            total_count=total_count,
            correct_count=total_correct,
            accuracy_rate=accuracy_rate,
            total_duration=total_duration,
            daily_breakdown=daily_breakdown,
        )

    @staticmethod
    async def _get_total_stats(db: AsyncSession, user_id: int) -> dict:
        """
        获取累计统计数据

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = (
            select(
                func.count(PracticeRecord.id).label('total_count'),
                func.sum(func.cast(PracticeRecord.is_correct, sa.Integer)).label('correct_count'),
            )
            .where(PracticeRecord.user_id == user_id)
        )

        result = await db.execute(stmt)
        row = result.one()

        total_count = row.total_count or 0
        correct_count = row.correct_count or 0

        accuracy_rate = (
            Decimal((correct_count / total_count) * 100).quantize(Decimal('0.01'))
            if total_count > 0
            else Decimal('0')
        )

        return {
            'total_count': total_count,
            'correct_count': correct_count,
            'accuracy_rate': accuracy_rate,
        }


home_service: HomeService = HomeService()
