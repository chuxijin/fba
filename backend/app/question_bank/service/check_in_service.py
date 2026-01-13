#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""打卡服务类"""
import calendar
from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank.crud.crud_check_in import check_in_dao
from backend.app.question_bank.model import PracticeRecord, UserCheckIn
from backend.app.question_bank.schema.home import CheckInCalendarData, CheckInCalendarDay, CheckInInfo


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
    async def check_in(
        *, db: AsyncSession, user_id: int, practice_count: int, practice_duration: int
    ) -> None:
        """
        用户打卡

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param practice_count: 当日做题数
        :param practice_duration: 当日练习时长
        """
        await check_in_dao.check_in(db, user_id, practice_count, practice_duration)

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
        today_start = datetime.combine(date.today(), datetime.min.time())
        stmt = (
            select(func.count(PracticeRecord.id))
            .where(
                PracticeRecord.user_id == user_id,
                PracticeRecord.created_time >= today_start,
            )
        )
        result = await db.scalar(stmt)
        return result or 0


check_in_service: CheckInService = CheckInService()
