#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio

from datetime import date, datetime, timedelta
from decimal import Decimal

import sqlalchemy as sa

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.model import PracticeRecord, PracticeSession, UserCheckIn, UserPracticeStats
from backend.app.question_bank.schema.home import (
    CheckInInfo,
    DailyPractice,
    HomeDashboardData,
    HomeUserReportData,
    WeekPracticeStats,
)
from backend.app.question_bank.service.rank_service import rank_service
from backend.database.db import async_db_session
from backend.utils.timezone import timezone


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
        today = timezone.now().date()

        # 5 个独立查询并发执行，每个使用独立 session 避免单连接串行
        async def _run_check_in() -> tuple[list[date], int]:
            async with async_db_session() as session:
                return await HomeService._get_check_in_summary(session, user_id)

        async def _run_week() -> WeekPracticeStats:
            async with async_db_session() as session:
                return await HomeService._get_week_stats(session, user_id)

        async def _run_rank():
            async with async_db_session() as session:
                return await rank_service.get_user_rank_info(db=session, user_id=user_id)

        async def _run_total_and_answer_rank() -> tuple[dict, dict]:
            async with async_db_session() as session:
                return await HomeService._get_total_and_answer_rank(session, user_id)

        async def _run_session_count() -> int:
            async with async_db_session() as session:
                return await HomeService._get_created_session_count(session, user_id)

        (
            (recent_dates, total_check_in_days),
            week_stats,
            rank_info,
            (total_stats, answer_rank_stats),
            created_session_count,
        ) = await asyncio.gather(
            _run_check_in(),
            _run_week(),
            _run_rank(),
            _run_total_and_answer_rank(),
            _run_session_count(),
        )

        is_checked_in = bool(recent_dates) and recent_dates[0] == today
        streak = HomeService._calc_streak(recent_dates, today)
        today_daily = next((d for d in week_stats.daily_breakdown if d.date == today), None)

        check_in_info = CheckInInfo(
            check_in_streak=streak,
            total_check_in_days=total_check_in_days,
            is_checked_in_today=is_checked_in,
            today_practice_count=today_daily.count if today_daily else 0,
        )

        report = HomeUserReportData(
            total_answer_count=total_stats['total_count'],
            accuracy_rate=total_stats['accuracy_rate'],
            site_max_answer_count=answer_rank_stats['site_max_answer_count'],
            answer_count_rank=answer_rank_stats['answer_count_rank'],
            practice_days=total_stats['practice_days'],
            total_answer_duration=total_stats['total_duration'],
            created_session_count=created_session_count,
        )

        return HomeDashboardData(
            check_in=check_in_info,
            week_stats=week_stats,
            rank=rank_info,
            total_questions=total_stats['total_count'],
            total_correct=total_stats['correct_count'],
            overall_accuracy=total_stats['accuracy_rate'],
            report=report,
        )

    # ------------------------------------------------------------------
    #  打卡相关
    # ------------------------------------------------------------------

    @staticmethod
    async def _get_check_in_summary(db: AsyncSession, user_id: int) -> tuple[list[date], int]:
        """
        获取打卡摘要：最近打卡日期列表 + 总打卡天数（单条 SQL 合并）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        # 用窗口函数一次性拿到 LIMIT 365 的最近日期 + 总条数，省一个 RTT
        stmt = (
            select(
                UserCheckIn.check_date,
                func.count().over().label('total_days'),
            )
            .where(UserCheckIn.user_id == user_id)
            .order_by(UserCheckIn.check_date.desc())
            .limit(365)
        )
        rows = (await db.execute(stmt)).all()

        if not rows:
            return [], 0

        recent_dates = [row.check_date for row in rows]
        total_days = int(rows[0].total_days)
        return recent_dates, total_days

    @staticmethod
    def _calc_streak(dates: list[date], today: date) -> int:
        """
        从已排序的打卡日期计算连续天数

        :param dates: 打卡日期列表（降序）
        :param today: 今日日期
        :return:
        """
        if not dates:
            return 0

        streak = 0
        current_date = today

        for check_date in dates:
            if check_date == current_date:
                streak += 1
                current_date -= timedelta(days=1)
            elif check_date == current_date - timedelta(days=1):
                streak += 1
                current_date = check_date - timedelta(days=1)
            else:
                break

        return streak

    # ------------------------------------------------------------------
    #  本周统计
    # ------------------------------------------------------------------

    @staticmethod
    async def _get_week_stats(db: AsyncSession, user_id: int) -> WeekPracticeStats:
        """获取本周刷题统计"""
        today = timezone.now().date()
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

    # ------------------------------------------------------------------
    #  累计统计 & 排名
    # ------------------------------------------------------------------

    @staticmethod
    async def _get_total_and_answer_rank(db: AsyncSession, user_id: int) -> tuple[dict, dict]:
        """
        合并查询用户快照统计 + 全站答题量排名（单条 SQL）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        # CTE 物化用户行一次，后续标量子查询复用，避免重复 PK lookup
        me_cte = (
            select(
                UserPracticeStats.total_count,
                UserPracticeStats.correct_count,
                UserPracticeStats.total_duration,
                UserPracticeStats.practice_days,
            )
            .where(UserPracticeStats.user_id == user_id)
            .cte('me_stats')
        )

        my_total_expr = func.coalesce(select(me_cte.c.total_count).scalar_subquery(), 0)

        stmt = select(
            my_total_expr.label('my_total'),
            func.coalesce(select(me_cte.c.correct_count).scalar_subquery(), 0).label('my_correct'),
            func.coalesce(select(me_cte.c.total_duration).scalar_subquery(), 0).label('my_duration'),
            func.coalesce(select(me_cte.c.practice_days).scalar_subquery(), 0).label('my_days'),
            func.coalesce(func.max(UserPracticeStats.total_count), 0).label('site_max'),
            func.coalesce(
                func.sum(sa.case((UserPracticeStats.total_count > my_total_expr, 1), else_=0)),
                0,
            ).label('higher_count'),
        ).select_from(UserPracticeStats)

        row = (await db.execute(stmt)).one()

        my_total = int(row.my_total)
        my_correct = int(row.my_correct)
        accuracy_rate = (
            Decimal((my_correct / my_total) * 100).quantize(Decimal('0.01'))
            if my_total > 0
            else Decimal('0')
        )

        total_stats = {
            'total_count': my_total,
            'correct_count': my_correct,
            'accuracy_rate': accuracy_rate,
            'total_duration': int(row.my_duration),
            'practice_days': int(row.my_days),
        }
        rank_stats = {
            'site_max_answer_count': int(row.site_max),
            'answer_count_rank': int(row.higher_count) + 1 if my_total > 0 else 0,
        }
        return total_stats, rank_stats

    @staticmethod
    async def _get_created_session_count(db: AsyncSession, user_id: int) -> int:
        """获取用户创建的会话总数"""
        stmt = select(func.count(PracticeSession.id)).where(
            PracticeSession.user_id == user_id,
            PracticeSession.del_flag.is_(False),
        )
        result = await db.scalar(stmt)
        return int(result or 0)


home_service: HomeService = HomeService()
