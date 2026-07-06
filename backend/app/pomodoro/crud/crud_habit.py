#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date

from sqlalchemy import Select, extract, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.pomodoro.enums import PomodoroHabitStatus
from backend.app.pomodoro.model.habit import PomodoroHabit, PomodoroHabitCheckin


class CRUDPomodoroHabit(CRUDPlus[PomodoroHabit]):
    """番茄习惯数据库操作类"""

    async def get_by_user(self, db: AsyncSession, user_id: int, habit_id: int) -> PomodoroHabit | None:
        """
        获取用户习惯

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param habit_id: 习惯 ID
        :return:
        """
        return await self.select_model_by_column(db, id__eq=habit_id, user_id__eq=user_id)

    async def get_select_by_user(
        self,
        user_id: int,
        status: PomodoroHabitStatus | None = None,
    ) -> Select:
        """
        获取用户习惯查询

        :param user_id: 用户 ID
        :param status: 习惯状态
        :return:
        """
        stmt = select(PomodoroHabit).where(PomodoroHabit.user_id == user_id)
        if status is not None:
            stmt = stmt.where(PomodoroHabit.status == status.value)

        return stmt.order_by(PomodoroHabit.status.asc(), PomodoroHabit.created_time.desc())


class CRUDPomodoroHabitCheckin(CRUDPlus[PomodoroHabitCheckin]):
    """番茄习惯打卡数据库操作类"""

    async def get_by_habit_and_date(
        self,
        db: AsyncSession,
        user_id: int,
        habit_id: int,
        checkin_date: date,
    ) -> PomodoroHabitCheckin | None:
        """
        获取习惯当日打卡

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param habit_id: 习惯 ID
        :param checkin_date: 打卡日期
        :return:
        """
        return await self.select_model_by_column(
            db,
            user_id__eq=user_id,
            habit_id__eq=habit_id,
            checkin_date__eq=checkin_date,
        )

    async def get_by_habits_and_date(
        self,
        db: AsyncSession,
        user_id: int,
        habit_ids: list[int],
        checkin_date: date,
    ) -> list[PomodoroHabitCheckin]:
        """
        获取多个习惯当日打卡

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param habit_ids: 习惯 ID 列表
        :param checkin_date: 打卡日期
        :return:
        """
        if not habit_ids:
            return []

        stmt = select(PomodoroHabitCheckin).where(
            PomodoroHabitCheckin.user_id == user_id,
            PomodoroHabitCheckin.habit_id.in_(habit_ids),
            PomodoroHabitCheckin.checkin_date == checkin_date,
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_select_by_user(
        self,
        user_id: int,
        year: int | None = None,
        month: int | None = None,
    ) -> Select:
        """
        获取用户习惯打卡查询

        :param user_id: 用户 ID
        :param year: 年份
        :param month: 月份
        :return:
        """
        stmt = select(PomodoroHabitCheckin).where(PomodoroHabitCheckin.user_id == user_id)
        if year is not None:
            stmt = stmt.where(extract('year', PomodoroHabitCheckin.checkin_date) == year)
        if month is not None:
            stmt = stmt.where(extract('month', PomodoroHabitCheckin.checkin_date) == month)

        return stmt.order_by(PomodoroHabitCheckin.checkin_date.desc(), PomodoroHabitCheckin.created_time.desc())


pomodoro_habit_dao: CRUDPomodoroHabit = CRUDPomodoroHabit(PomodoroHabit)
pomodoro_habit_checkin_dao: CRUDPomodoroHabitCheckin = CRUDPomodoroHabitCheckin(PomodoroHabitCheckin)
