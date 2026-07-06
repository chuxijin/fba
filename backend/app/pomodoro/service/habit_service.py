#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.pomodoro.crud.crud_habit import pomodoro_habit_checkin_dao, pomodoro_habit_dao
from backend.app.pomodoro.enums import PomodoroHabitStatus
from backend.app.pomodoro.model.habit import PomodoroHabit, PomodoroHabitCheckin
from backend.app.pomodoro.schema.habit import (
    CheckinPomodoroHabitParam,
    CreatePomodoroHabitCheckinInternal,
    CreatePomodoroHabitInternal,
    CreatePomodoroHabitParam,
    GetPomodoroHabitDetail,
    UpdatePomodoroHabitParam,
)
from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.utils.timezone import timezone


class PomodoroHabitService:
    """番茄习惯服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, user_id: int, habit_id: int) -> PomodoroHabit:
        """
        获取习惯

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param habit_id: 习惯 ID
        :return:
        """
        habit = await pomodoro_habit_dao.get_by_user(db, user_id, habit_id)
        if not habit:
            raise errors.NotFoundError(msg='习惯不存在或无权访问')
        return habit

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        user_id: int,
        status: PomodoroHabitStatus | None = None,
    ) -> dict:
        """
        获取习惯分页列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param status: 习惯状态
        :return:
        """
        stmt = await pomodoro_habit_dao.get_select_by_user(user_id=user_id, status=status)
        data = await paging_data(db, stmt, schema_cls=GetPomodoroHabitDetail)
        await PomodoroHabitService._fill_today_checkin_status(db=db, user_id=user_id, page_data=data)
        return data

    @staticmethod
    async def create(*, db: AsyncSession, user_id: int, obj: CreatePomodoroHabitParam) -> PomodoroHabit:
        """
        创建习惯

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param obj: 创建参数
        :return:
        """
        data = CreatePomodoroHabitInternal(user_id=user_id, **obj.model_dump(mode='python'))
        habit = await pomodoro_habit_dao.create_model(db, data, commit=False)
        await db.flush()
        await db.refresh(habit)
        return habit

    @staticmethod
    async def update(
        *,
        db: AsyncSession,
        user_id: int,
        habit_id: int,
        obj: UpdatePomodoroHabitParam,
    ) -> PomodoroHabit:
        """
        更新习惯

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param habit_id: 习惯 ID
        :param obj: 更新参数
        :return:
        """
        habit = await PomodoroHabitService.get(db=db, user_id=user_id, habit_id=habit_id)
        update_data = obj.model_dump(mode='python', exclude_unset=True)
        if not update_data:
            return habit

        await pomodoro_habit_dao.update_model(db, habit.id, update_data, commit=False)
        await db.flush()
        await db.refresh(habit)
        return habit

    @staticmethod
    async def disable(*, db: AsyncSession, user_id: int, habit_id: int) -> PomodoroHabit:
        """
        关闭习惯

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param habit_id: 习惯 ID
        :return:
        """
        habit = await PomodoroHabitService.get(db=db, user_id=user_id, habit_id=habit_id)
        await pomodoro_habit_dao.update_model(
            db,
            habit.id,
            {'status': PomodoroHabitStatus.disabled.value},
            commit=False,
        )
        await db.flush()
        await db.refresh(habit)
        return habit

    @staticmethod
    async def checkin(
        *,
        db: AsyncSession,
        user_id: int,
        habit_id: int,
        obj: CheckinPomodoroHabitParam,
    ) -> PomodoroHabitCheckin:
        """
        习惯打卡

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param habit_id: 习惯 ID
        :param obj: 打卡参数
        :return:
        """
        habit = await PomodoroHabitService.get(db=db, user_id=user_id, habit_id=habit_id)
        if habit.status != PomodoroHabitStatus.enabled.value:
            raise errors.ForbiddenError(msg='习惯已关闭，不能打卡')

        now = timezone.now()
        checkin_date = obj.checkin_date or now.date()

        if habit.repeat_days:
            weekday = str(checkin_date.weekday())
            if weekday not in habit.repeat_days.split(','):
                raise errors.ForbiddenError(msg='今天不是该习惯的打卡日')
        checkin = await pomodoro_habit_checkin_dao.get_by_habit_and_date(db, user_id, habit_id, checkin_date)
        if checkin:
            await pomodoro_habit_checkin_dao.update_model(
                db,
                checkin.id,
                {
                    'count': checkin.count + obj.count,
                    'checked_at': now,
                },
                commit=False,
            )
            await db.flush()
            await db.refresh(checkin)
            return checkin

        data = CreatePomodoroHabitCheckinInternal(
            user_id=user_id,
            habit_id=habit_id,
            checkin_date=checkin_date,
            checked_at=now,
            count=obj.count,
        )
        checkin = await pomodoro_habit_checkin_dao.create_model(db, data, commit=False)
        await db.flush()
        await db.refresh(checkin)
        return checkin

    @staticmethod
    async def get_checkin_history(
        *,
        db: AsyncSession,
        user_id: int,
        year: int | None = None,
        month: int | None = None,
    ) -> dict:
        """
        获取习惯打卡历史

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param year: 年份
        :param month: 月份
        :return:
        """
        stmt = await pomodoro_habit_checkin_dao.get_select_by_user(user_id=user_id, year=year, month=month)
        return await paging_data(db, stmt)

    @staticmethod
    async def _fill_today_checkin_status(*, db: AsyncSession, user_id: int, page_data: dict) -> None:
        """
        填充今日习惯打卡状态

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param page_data: 分页数据
        :return:
        """
        items = page_data.get('items')
        if not isinstance(items, list) or not items:
            return

        habit_ids = [int(item['id']) for item in items if isinstance(item, dict) and item.get('id')]
        checkins = await pomodoro_habit_checkin_dao.get_by_habits_and_date(
            db,
            user_id=user_id,
            habit_ids=habit_ids,
            checkin_date=timezone.now().date(),
        )
        checkin_count_map = {checkin.habit_id: checkin.count for checkin in checkins}

        for item in items:
            if not isinstance(item, dict):
                continue

            checkin_count = checkin_count_map.get(int(item['id']), 0)
            checked_today = checkin_count > 0
            item['checkin_count'] = checkin_count
            item['today_checkin_count'] = checkin_count
            item['checked_today'] = checked_today
            item['is_checked_today'] = checked_today


pomodoro_habit_service: PomodoroHabitService = PomodoroHabitService()
