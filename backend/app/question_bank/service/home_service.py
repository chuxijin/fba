#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""首页 Dashboard 服务类"""
from datetime import date, datetime, timedelta
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.model import PracticeRecord, PracticeSession
from backend.app.question_bank.schema.home import (
    DailyPractice,
    HomeDashboardData,
    HomeUserReportData,
    WeekPracticeStats,
)
from backend.app.question_bank.service.check_in_service import check_in_service
from backend.app.question_bank.service.rank_service import rank_service


class HomeService:
    """首页 Dashboard 服务类"""

    @staticmethod
    async def get_dashboard_data(*, db: AsyncSession, user_id: int) -> HomeDashboardData:
        """
        获取首页 Dashboard 数据

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        check_in_info = await check_in_service.get_check_in_info(db=db, user_id=user_id)
        week_stats = await HomeService._get_week_stats(db, user_id)
        rank_info = await rank_service.get_user_rank_info(db=db, user_id=user_id)
        total_stats = await HomeService._get_total_stats(db, user_id)
        report_stats = await HomeService._get_report_stats(db, user_id, total_stats)

        return HomeDashboardData(
            check_in=check_in_info,
            week_stats=week_stats,
            rank=rank_info,
            total_questions=total_stats['total_count'],
            total_correct=total_stats['correct_count'],
            overall_accuracy=total_stats['accuracy_rate'],
            report=report_stats,
        )

    @staticmethod
    async def _get_week_stats(db: AsyncSession, user_id: int) -> WeekPracticeStats:
        """获取本周刷题统计"""
        today = date.today()
        week_start = today - timedelta(days=today.weekday())
        week_start_dt = datetime.combine(week_start, datetime.min.time())

        stmt = (
            select(
                func.date(PracticeRecord.created_time).label('practice_date'),
                func.count(PracticeRecord.id).label('count'),
                func.coalesce(func.sum(func.cast(PracticeRecord.is_correct, sa.Integer)), 0).label('correct_count'),
                func.coalesce(func.sum(PracticeRecord.answer_time), 0).label('duration'),
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
        """获取累计统计数据"""
        stmt = (
            select(
                func.count(PracticeRecord.id).label('total_count'),
                func.coalesce(func.sum(func.cast(PracticeRecord.is_correct, sa.Integer)), 0).label('correct_count'),
                func.coalesce(func.sum(PracticeRecord.answer_time), 0).label('total_duration'),
                func.count(sa.distinct(func.date(PracticeRecord.created_time))).label('practice_days'),
            )
            .where(PracticeRecord.user_id == user_id)
        )

        result = await db.execute(stmt)
        row = result.one()

        total_count = row.total_count or 0
        correct_count = row.correct_count or 0
        total_duration = row.total_duration or 0
        practice_days = row.practice_days or 0

        accuracy_rate = (
            Decimal((correct_count / total_count) * 100).quantize(Decimal('0.01'))
            if total_count > 0
            else Decimal('0')
        )

        return {
            'total_count': total_count,
            'correct_count': correct_count,
            'accuracy_rate': accuracy_rate,
            'total_duration': total_duration,
            'practice_days': practice_days,
        }

    @staticmethod
    async def _get_report_stats(
        db: AsyncSession,
        user_id: int,
        total_stats: dict,
    ) -> HomeUserReportData:
        """获取用户报告统计"""
        created_session_count = await HomeService._get_created_session_count(db, user_id)
        answer_rank_stats = await HomeService._get_answer_rank_stats(db, total_stats['total_count'])

        return HomeUserReportData(
            total_answer_count=total_stats['total_count'],
            accuracy_rate=total_stats['accuracy_rate'],
            site_max_answer_count=answer_rank_stats['site_max_answer_count'],
            answer_count_rank=answer_rank_stats['answer_count_rank'],
            practice_days=total_stats['practice_days'],
            total_answer_duration=total_stats['total_duration'],
            created_session_count=created_session_count,
        )

    @staticmethod
    async def _get_created_session_count(db: AsyncSession, user_id: int) -> int:
        stmt = select(func.count(PracticeSession.id)).where(PracticeSession.user_id == user_id)
        result = await db.scalar(stmt)
        return int(result or 0)

    @staticmethod
    async def _get_answer_rank_stats(db: AsyncSession, total_answer_count: int) -> dict:
        user_answer_count_subquery = (
            select(
                PracticeRecord.user_id.label('user_id'),
                func.count(PracticeRecord.id).label('practice_count'),
            )
            .group_by(PracticeRecord.user_id)
            .subquery()
        )

        site_max_stmt = select(func.coalesce(func.max(user_answer_count_subquery.c.practice_count), 0))
        site_max_answer_count = int((await db.scalar(site_max_stmt)) or 0)

        if total_answer_count <= 0:
            return {
                'site_max_answer_count': site_max_answer_count,
                'answer_count_rank': 0,
            }

        higher_count_stmt = (
            select(func.count())
            .select_from(user_answer_count_subquery)
            .where(user_answer_count_subquery.c.practice_count > total_answer_count)
        )
        higher_count = int((await db.scalar(higher_count_stmt)) or 0)

        return {
            'site_max_answer_count': site_max_answer_count,
            'answer_count_rank': higher_count + 1,
        }


home_service: HomeService = HomeService()
