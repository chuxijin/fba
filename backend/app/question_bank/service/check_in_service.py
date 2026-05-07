#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打卡服务类"""
import calendar

from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.membership.crud.crud_experience_rule import membership_experience_rule_dao
from backend.app.membership.model.experience_rule import MembershipExperienceRule
from backend.app.membership.service.experience_service import membership_experience_service
from backend.app.question_bank.crud.crud_check_in import check_in_dao
from backend.app.question_bank.crud.crud_user_practice_stats import user_practice_stats_dao
from backend.app.question_bank.model import PracticeRecord, UserCheckIn, UserPracticeStats
from backend.app.question_bank.schema.home import CheckInCalendarData, CheckInCalendarDay, CheckInInfo, CheckInResult
from backend.common.exception import errors
from backend.utils.timezone import timezone


class CheckInService:
    """打卡服务类"""

    @staticmethod
    async def get_check_in_info(*, db: AsyncSession, user_id: int) -> CheckInInfo:
        """
        获取用户打卡信息

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        is_checked_in = await check_in_dao.is_checked_in_today(db, user_id)
        streak = await check_in_dao.get_streak(db, user_id)
        total_days = await check_in_dao.get_total_days(db, user_id)
        today_count = await CheckInService._get_today_practice_count(db, user_id)

        return CheckInInfo(
            check_in_streak=streak,
            total_check_in_days=total_days,
            is_checked_in_today=is_checked_in,
            today_practice_count=today_count,
        )

    @staticmethod
    async def _get_reward_context(
        *, db: AsyncSession, user_id: int
    ) -> tuple[str, int, MembershipExperienceRule | None]:
        """
        获取签到奖励上下文

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        family_code = await membership_experience_service.resolve_reward_family(db, user_id=user_id)
        streak_before_today = await check_in_dao.get_streak(db, user_id)
        cycle_day = (streak_before_today % 7) + 1
        reward_rule = await membership_experience_rule_dao.get_active_rule(
            db,
            event_code='check_in',
            family_code=family_code,
            cycle_day=cycle_day,
        )
        return family_code, cycle_day, reward_rule

    @staticmethod
    async def try_auto_check_in(*, db: AsyncSession, user_id: int) -> CheckInResult | None:
        """
        达到条件后自动签到

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        today = timezone.now().date()
        today_summary = await CheckInService._get_today_practice_summary(db, user_id)
        existing = await check_in_dao.get_by_user_and_date(db, user_id, today)
        if existing:
            return None

        _, _, reward_rule = await CheckInService._get_reward_context(db=db, user_id=user_id)
        if not reward_rule:
            return None
        if today_summary['practice_count'] < reward_rule.min_practice_count:
            return None
        if today_summary['practice_duration'] < reward_rule.min_practice_duration:
            return None

        try:
            return await CheckInService.check_in(
                db=db,
                user_id=user_id,
                practice_count=today_summary['practice_count'],
                practice_duration=today_summary['practice_duration'],
            )
        except errors.RequestError:
            return None

    @staticmethod
    async def check_in(
        *, db: AsyncSession, user_id: int, practice_count: int, practice_duration: int
    ) -> CheckInResult:
        """
        用户打卡

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param practice_count: 当日做题数
        :param practice_duration: 当日练习时长
        """
        today = timezone.now().date()
        today_summary = await CheckInService._get_today_practice_summary(db, user_id)
        practice_count = today_summary['practice_count']
        practice_duration = today_summary['practice_duration']

        existing = await check_in_dao.get_by_user_and_date(db, user_id, today)
        if existing:
            streak = await check_in_dao.get_streak(db, user_id)
            total_days = await check_in_dao.get_total_days(db, user_id)
            return CheckInResult(
                is_checked_in_today=True,
                is_already_checked_in=True,
                check_in_streak=streak,
                total_check_in_days=total_days,
                practice_count=practice_count,
                practice_duration=practice_duration,
                reward_exp=0,
            )

        family_code, cycle_day, reward_rule = await CheckInService._get_reward_context(db=db, user_id=user_id)
        if reward_rule and practice_count < reward_rule.min_practice_count:
            raise errors.RequestError(msg=f'今日做题满 {reward_rule.min_practice_count} 题后可签到')
        if reward_rule and practice_duration < reward_rule.min_practice_duration:
            minutes = max(1, reward_rule.min_practice_duration // 60)
            raise errors.RequestError(msg=f'今日练习满 {minutes} 分钟后可签到')

        await check_in_dao.check_in(db, user_id, practice_count, practice_duration)

        reward_exp = reward_rule.exp_delta if reward_rule else 0
        progress: dict[str, int | str | None] | None = None
        if reward_exp > 0:
            progress = await membership_experience_service.add_experience(
                db,
                user_id=user_id,
                family_code=family_code,
                exp_delta=reward_exp,
                source='check_in',
                source_key=f'check_in:{user_id}:{today.isoformat()}',
                remark=f'连续签到第 {cycle_day} 天奖励',
            )

        streak = await check_in_dao.get_streak(db, user_id)
        total_days = await check_in_dao.get_total_days(db, user_id)

        # 同步连续打卡天数到快照表
        await CheckInService._sync_streak_days(db, user_id, streak)

        return CheckInResult(
            is_checked_in_today=True,
            is_already_checked_in=False,
            check_in_streak=streak,
            total_check_in_days=total_days,
            practice_count=practice_count,
            practice_duration=practice_duration,
            reward_exp=reward_exp,
            family_code=family_code,
            tier_grade=progress.get('tier_grade') if progress else None,
            exp=progress.get('exp') if progress else None,
            available_exp=progress.get('available_exp') if progress else None,
        )

    @staticmethod
    async def get_check_in_calendar(
        *, db: AsyncSession, user_id: int, year: int, month: int
    ) -> CheckInCalendarData:
        """
        获取打卡日历数据

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param year: 年份
        :param month: 月份（1-12）
        :return:
        """
        _, days_in_month = calendar.monthrange(year, month)
        month_start = date(year, month, 1)
        month_end = date(year, month, days_in_month)

        stmt = select(UserCheckIn).where(
            UserCheckIn.user_id == user_id,
            UserCheckIn.check_date >= month_start,
            UserCheckIn.check_date <= month_end,
        )
        result = await db.execute(stmt)
        check_in_records = result.scalars().all()

        check_in_map = {record.check_date: record for record in check_in_records}

        calendar_days = []
        for day in range(1, days_in_month + 1):
            current_date = date(year, month, day)
            record = check_in_map.get(current_date)

            calendar_days.append(
                CheckInCalendarDay(
                    date=current_date,
                    is_checked_in=record is not None,
                    practice_count=record.practice_count if record else 0,
                )
            )

        return CheckInCalendarData(
            year=year,
            month=month,
            days=calendar_days,
            total_check_in_days=len(check_in_records),
        )

    @staticmethod
    async def _get_today_practice_count(db: AsyncSession, user_id: int) -> int:
        """
        获取今日做题数（实时查询）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        today_start = datetime.combine(timezone.now().date(), datetime.min.time())
        stmt = (
            select(func.count(PracticeRecord.id))
            .where(
                PracticeRecord.user_id == user_id,
                PracticeRecord.created_time >= today_start,
            )
        )
        result = await db.scalar(stmt)
        return result or 0

    @staticmethod
    async def _get_today_practice_summary(db: AsyncSession, user_id: int) -> dict[str, int]:
        """
        获取今日练习摘要

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        today_start = datetime.combine(timezone.now().date(), datetime.min.time())
        stmt = select(
            func.count(PracticeRecord.id).label('practice_count'),
            func.coalesce(func.sum(PracticeRecord.answer_time), 0).label('practice_duration'),
        ).where(
            PracticeRecord.user_id == user_id,
            PracticeRecord.created_time >= today_start,
        )
        row = (await db.execute(stmt)).one()
        return {
            'practice_count': int(row.practice_count or 0),
            'practice_duration': int(row.practice_duration or 0),
        }


    @staticmethod
    async def _sync_streak_days(db: AsyncSession, user_id: int, streak: int) -> None:
        """
        同步连续打卡天数到快照表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param streak: 连续打卡天数
        """
        stats = await user_practice_stats_dao.get_or_create(db, user_id)
        if stats.streak_days != streak:
            from sqlalchemy import update as sa_update

            stmt = (
                sa_update(UserPracticeStats)
                .where(UserPracticeStats.id == stats.id)
                .values(streak_days=streak)
            )
            await db.execute(stmt)
            await db.flush()


check_in_service: CheckInService = CheckInService()
