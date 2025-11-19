#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.jia.crud.crud_habits import habit_dao, habit_record_dao
from backend.app.jia.model.habits import Habit, HabitRecord
from backend.app.jia.schema.habits import CreateHabitParam, CreateHabitRecordParam, UpdateHabitParam, UpdateHabitRecordParam
from backend.common.exception import errors


class HabitService:
    """习惯服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> Habit:
        """
        获取习惯详情

        :param db: 数据库会话
        :param pk: 习惯 ID
        :return:
        """
        habit = await habit_dao.get(db, pk)
        if not habit:
            raise errors.NotFoundError(msg='习惯不存在')
        return habit

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        difficulty: int | None = None,
        target_type: str | None = None,
        is_archived: int | None = None,
        is_pinned: int | None = None,
        sync_status: str | None = None,
    ) -> list[Habit]:
        """
        获取习惯列表

        :param db: 数据库会话
        :param difficulty: 难度等级
        :param target_type: 目标类型
        :param is_archived: 是否归档
        :param is_pinned: 是否置顶
        :param sync_status: 同步状态
        :return:
        """
        select_stmt = await habit_dao.get_select(difficulty, target_type, is_archived, is_pinned, sync_status)
        habits = await db.execute(select_stmt)
        return list(habits.scalars().all())

    @staticmethod
    async def get_all(*, db: AsyncSession, user_id: int) -> list[Habit]:
        """
        获取所有习惯

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return list(await habit_dao.get_all(db, user_id))

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateHabitParam, user_id: int) -> None:
        """
        创建习惯

        :param db: 数据库会话
        :param obj: 创建习惯参数
        :param user_id: 用户 ID
        :return:
        """
        existing = await habit_dao.get_by_name(db, obj.name, user_id)
        if existing:
            raise errors.ConflictError(msg='习惯名称已存在')
        await habit_dao.create(db, obj, user_id)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateHabitParam, user_id: int) -> int:
        """
        更新习惯

        :param db: 数据库会话
        :param pk: 习惯 ID
        :param obj: 更新习惯参数
        :param user_id: 用户 ID
        :return:
        """
        habit = await habit_dao.get(db, pk)
        if not habit:
            raise errors.NotFoundError(msg='习惯不存在')
        if obj.name and obj.name != habit.name:
            existing = await habit_dao.get_by_name(db, obj.name, user_id)
            if existing:
                raise errors.ConflictError(msg='习惯名称已存在')
        count = await habit_dao.update(db, pk, obj, user_id)
        return count

    @staticmethod
    async def delete(*, db: AsyncSession, pks: list[int]) -> int:
        """
        批量删除习惯

        :param db: 数据库会话
        :param pks: 习惯 ID 列表
        :return:
        """
        count = await habit_dao.delete(db, pks)
        return count


class HabitRecordService:
    """习惯打卡记录服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> HabitRecord:
        """
        获取打卡记录详情

        :param db: 数据库会话
        :param pk: 记录 ID
        :return:
        """
        record = await habit_record_dao.get(db, pk)
        if not record:
            raise errors.NotFoundError(msg='打卡记录不存在')
        return record

    @staticmethod
    async def get_by_habit(*, db: AsyncSession, habit_id: int) -> list[HabitRecord]:
        """
        获取习惯的所有打卡记录

        :param db: 数据库会话
        :param habit_id: 习惯 ID
        :return:
        """
        return list(await habit_record_dao.get_by_habit(db, habit_id))

    @staticmethod
    async def get_by_habit_and_date(*, db: AsyncSession, habit_id: int, date: int) -> HabitRecord | None:
        """
        通过习惯和日期获取打卡记录

        :param db: 数据库会话
        :param habit_id: 习惯 ID
        :param date: 日期时间戳
        :return:
        """
        return await habit_record_dao.get_by_habit_and_date(db, habit_id, date)

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        habit_id: int | None = None,
        date_start: int | None = None,
        date_end: int | None = None,
        status: str | None = None,
        checkin_type: str | None = None,
    ) -> list[HabitRecord]:
        """
        获取打卡记录列表

        :param db: 数据库会话
        :param habit_id: 习惯 ID
        :param date_start: 开始日期时间戳
        :param date_end: 结束日期时间戳
        :param status: 状态
        :param checkin_type: 打卡类型
        :return:
        """
        select_stmt = await habit_record_dao.get_select(habit_id, date_start, date_end, status, checkin_type)
        records = await db.execute(select_stmt)
        return list(records.scalars().all())

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateHabitRecordParam, user_id: int) -> None:
        """
        创建打卡记录

        :param db: 数据库会话
        :param obj: 创建打卡记录参数
        :param user_id: 用户 ID
        :return:
        """
        habit = await habit_dao.get(db, obj.habit_id)
        if not habit:
            raise errors.NotFoundError(msg='习惯不存在')
        existing = await habit_record_dao.get_by_habit_and_date(db, obj.habit_id, obj.date)
        if existing:
            raise errors.ConflictError(msg='该日期已有打卡记录')
        await habit_record_dao.create(db, obj, user_id)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateHabitRecordParam, user_id: int) -> int:
        """
        更新打卡记录

        :param db: 数据库会话
        :param pk: 记录 ID
        :param obj: 更新打卡记录参数
        :param user_id: 用户 ID
        :return:
        """
        record = await habit_record_dao.get(db, pk)
        if not record:
            raise errors.NotFoundError(msg='打卡记录不存在')
        if obj.date is not None and obj.date != record.date:
            existing = await habit_record_dao.get_by_habit_and_date(db, record.habit_id, obj.date)
            if existing and existing.id != pk:
                raise errors.ConflictError(msg='该日期已有打卡记录')
        count = await habit_record_dao.update(db, pk, obj, user_id)
        return count

    @staticmethod
    async def delete(*, db: AsyncSession, pks: list[int]) -> int:
        """
        批量删除打卡记录

        :param db: 数据库会话
        :param pks: 记录 ID 列表
        :return:
        """
        count = await habit_record_dao.delete(db, pks)
        return count


habit_service: HabitService = HabitService()
habit_record_service: HabitRecordService = HabitRecordService()

