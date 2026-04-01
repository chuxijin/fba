#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date, datetime, timedelta
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_user_practice_stats import user_practice_stats_dao
from backend.app.question_bank.model import PracticeRecord, PracticeSession, UserCheckIn, UserPracticeStats
from backend.app.question_bank.schema.home import (
    CheckInInfo,
    DailyPractice,
    HomeDashboardData,
    HomeUserReportData,
    WeekPracticeStats,
)
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
        today = date.today()

        # 1. 打卡汇总：单次查询替代 3 次独立查询 (is_checked_in + streak + total_days)
        check_in_records = await HomeService._get_check_in_records(db, user_id)
        is_checked_in = bool(check_in_records) and check_in_records[0].check_date == today
        streak = HomeService._calc_streak(check_in_records, today)

        # 2. 本周统计（今日做题数从 daily_breakdown 中提取，省去独立查询）
        week_stats = await HomeService._get_week_stats(db, user_id)
        today_daily = next((d for d in week_stats.daily_breakdown if d.date == today), None)

        check_in_info = CheckInInfo(
            check_in_streak=streak,
            total_check_in_days=len(check_in_records),
            is_checked_in_today=is_checked_in,
            today_practice_count=today_daily.count if today_daily else 0,
        )

        # 3. 排名
        rank_info = await rank_service.get_user_rank_info(db=db, user_id=user_id)

        # 4. 快照统计
        total_stats = await HomeService._get_total_stats(db, user_id)

        # 5. 会话数 + 排名统计（合并 MAX/COUNT 为单次查询）
        created_session_count = await HomeService._get_created_session_count(db, user_id)
        answer_rank_stats = await HomeService._get_answer_rank_stats(db, total_stats['total_count'])

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
    async def _get_check_in_records(db: AsyncSession, user_id: int) -> list[UserCheckIn]:
        """获取用户全部打卡记录（按日期降序）"""
        stmt = (
            select(UserCheckIn)
            .where(UserCheckIn.user_id == user_id)
            .order_by(UserCheckIn.check_date.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    def _calc_streak(records: list[UserCheckIn], today: date) -> int:
        """从已排序的打卡记录计算连续天数"""
        if not records:
            return 0

        streak = 0
        current_date = today

        for record in records:
            if record.check_date == current_date:
                streak += 1
                current_date -= timedelta(days=1)
            elif record.check_date == current_date - timedelta(days=1):
                streak += 1
                current_date = record.check_date - timedelta(days=1)
            else:
                break

        return streak

    # ------------------------------------------------------------------
    #  本周统计
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    #  累计统计 & 排名
    # ------------------------------------------------------------------

    @staticmethod
    async def _get_total_stats(db: AsyncSession, user_id: int) -> dict:
        """从快照表获取累计统计数据"""
        stats = await user_practice_stats_dao.get_by_user(db, user_id)

        total_count = stats.total_count if stats else 0
        correct_count = stats.correct_count if stats else 0
        total_duration = stats.total_duration if stats else 0
        practice_days = stats.practice_days if stats else 0

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
    async def _get_created_session_count(db: AsyncSession, user_id: int) -> int:
        """获取用户创建的会话总数"""
        stmt = select(func.count(PracticeSession.id)).where(
            PracticeSession.user_id == user_id,
            PracticeSession.del_flag.is_(False),
        )
        result = await db.scalar(stmt)
        return int(result or 0)

    @staticmethod
    async def _get_answer_rank_stats(db: AsyncSession, total_answer_count: int) -> dict:
        """从快照表获取排名统计（合并 MAX + COUNT 为单次查询）"""
        if total_answer_count <= 0:
            site_max_stmt = select(func.coalesce(func.max(UserPracticeStats.total_count), 0))
            site_max = int((await db.scalar(site_max_stmt)) or 0)
            return {
                'site_max_answer_count': site_max,
                'answer_count_rank': 0,
            }

        stmt = (
            select(
                func.coalesce(func.max(UserPracticeStats.total_count), 0).label('site_max'),
                func.coalesce(
                    func.sum(sa.case((UserPracticeStats.total_count > total_answer_count, 1), else_=0)),
                    0,
                ).label('higher_count'),
            )
            .select_from(UserPracticeStats)
        )
        row = (await db.execute(stmt)).one()

        return {
            'site_max_answer_count': int(row.site_max),
            'answer_count_rank': int(row.higher_count) + 1,
        }


home_service: HomeService = HomeService()
