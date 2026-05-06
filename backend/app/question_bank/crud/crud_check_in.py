#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model import UserCheckIn
from backend.utils.timezone import timezone


class CRUDCheckIn(CRUDPlus[UserCheckIn]):
    """用户打卡数据库操作类"""

    async def get_by_user_and_date(
        self, db: AsyncSession, user_id: int, check_date: date
    ) -> UserCheckIn | None:
        """
        获取用户指定日期的打卡记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param check_date: 打卡日期
        :return:
        """
        return await self.select_model_by_column(db, user_id=user_id, check_date=check_date)

    async def is_checked_in_today(self, db: AsyncSession, user_id: int) -> bool:
        """
        判断用户今天是否已打卡

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        today = timezone.now().date()
        record = await self.get_by_user_and_date(db, user_id, today)
        return record is not None

    async def check_in(
        self, db: AsyncSession, user_id: int, practice_count: int, practice_duration: int
    ) -> UserCheckIn:
        """
        用户打卡

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param practice_count: 当日做题数
        :param practice_duration: 当日练习时长
        :return:
        """
        today = timezone.now().date()
        existing = await self.get_by_user_and_date(db, user_id, today)

        if existing:
            await self.update_model(
                db,
                existing.id,
                {
                    'practice_count': practice_count,
                    'practice_duration': practice_duration,
                },
            )
            await db.refresh(existing)
            return existing

        new_check_in = self.model(
            user_id=user_id,
            check_date=today,
            practice_count=practice_count,
            practice_duration=practice_duration,
        )
        db.add(new_check_in)
        await db.flush()
        await db.refresh(new_check_in)
        return new_check_in

    async def get_streak(self, db: AsyncSession, user_id: int) -> int:
        """
        获取连续打卡天数

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = (
            select(UserCheckIn)
            .where(UserCheckIn.user_id == user_id)
            .order_by(UserCheckIn.check_date.desc())
        )
        result = await db.execute(stmt)
        records = result.scalars().all()

        if not records:
            return 0

        streak = 0
        current_date = timezone.now().date()

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

    async def get_total_days(self, db: AsyncSession, user_id: int) -> int:
        """
        获取累计打卡天数

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = (
            select(func.count(UserCheckIn.id))
            .where(UserCheckIn.user_id == user_id)
        )
        result = await db.scalar(stmt)
        return result or 0


check_in_dao: CRUDCheckIn = CRUDCheckIn(UserCheckIn)
