#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.jia.model.habits import Habit, HabitRecord
from backend.app.jia.schema.habits import CreateHabitParam, CreateHabitRecordParam, UpdateHabitParam, UpdateHabitRecordParam


class CRUDHabit(CRUDPlus[Habit]):
    """习惯数据库操作类"""

    async def get(self, db: AsyncSession, habit_id: int) -> Habit | None:
        """
        获取习惯详情

        :param db: 数据库会话
        :param habit_id: 习惯 ID
        :return:
        """
        return await self.select_model_by_column(db, id=habit_id, deleted_at=None)

    async def get_by_server_id(self, db: AsyncSession, server_id: str) -> Habit | None:
        """
        通过服务器 ID 获取习惯

        :param db: 数据库会话
        :param server_id: 服务器 ID
        :return:
        """
        return await self.select_model_by_column(db, server_id=server_id, deleted_at=None)

    async def get_by_name(self, db: AsyncSession, name: str, user_id: int) -> Habit | None:
        """
        通过名称获取习惯

        :param db: 数据库会话
        :param name: 习惯名称
        :param user_id: 用户 ID
        :return:
        """
        return await self.select_model_by_column(db, name=name, created_by=user_id, deleted_at=None)

    async def get_select(
        self,
        difficulty: int | None,
        target_type: str | None,
        is_archived: int | None,
        is_pinned: int | None,
        sync_status: str | None,
    ) -> Select:
        """
        获取习惯列表查询表达式

        :param difficulty: 难度等级
        :param target_type: 目标类型
        :param is_archived: 是否归档
        :param is_pinned: 是否置顶
        :param sync_status: 同步状态
        :return:
        """
        filters = {'deleted_at': None}

        if difficulty is not None:
            filters['difficulty'] = difficulty
        if target_type is not None:
            filters['target_type'] = target_type
        if is_archived is not None:
            filters['is_archived'] = is_archived
        if is_pinned is not None:
            filters['is_pinned'] = is_pinned
        if sync_status is not None:
            filters['sync_status'] = sync_status

        return await self.select_order('created_time', 'desc', **filters)

    async def get_all(self, db: AsyncSession, user_id: int) -> Sequence[Habit]:
        """
        获取所有习惯

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await self.select_models_order(db, 'created_time', 'desc', created_by=user_id, deleted_at=None)

    async def create(self, db: AsyncSession, obj: CreateHabitParam, user_id: int) -> Habit:
        """
        创建习惯

        :param db: 数据库会话
        :param obj: 创建习惯参数
        :param user_id: 用户 ID
        :return:
        """
        dict_obj = obj.model_dump()
        dict_obj['created_by'] = user_id
        return await self.create_model(db, dict_obj, commit=False)

    async def update(self, db: AsyncSession, habit_id: int, obj: UpdateHabitParam, user_id: int) -> int:
        """
        更新习惯

        :param db: 数据库会话
        :param habit_id: 习惯 ID
        :param obj: 更新习惯参数
        :param user_id: 用户 ID
        :return:
        """
        dict_obj = obj.model_dump(exclude_unset=True)
        dict_obj['updated_by'] = user_id
        return await self.update_model(db, habit_id, dict_obj)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        """
        批量软删除习惯

        :param db: 数据库会话
        :param pks: 习惯 ID 列表
        :return:
        """
        import time
        deleted_at = int(time.time())
        count = 0
        for pk in pks:
            count += await self.update_model_by_column(db, {'deleted_at': deleted_at}, id=pk)
        return count


class CRUDHabitRecord(CRUDPlus[HabitRecord]):
    """习惯打卡记录数据库操作类"""

    async def get(self, db: AsyncSession, record_id: int) -> HabitRecord | None:
        """
        获取打卡记录详情

        :param db: 数据库会话
        :param record_id: 记录 ID
        :return:
        """
        return await self.select_model_by_column(db, id=record_id, deleted_at=None)

    async def get_by_habit_and_date(self, db: AsyncSession, habit_id: int, date: int) -> HabitRecord | None:
        """
        通过习惯和日期获取打卡记录

        :param db: 数据库会话
        :param habit_id: 习惯 ID
        :param date: 日期时间戳
        :return:
        """
        return await self.select_model_by_column(db, habit_id=habit_id, date=date, deleted_at=None)

    async def get_by_habit(self, db: AsyncSession, habit_id: int) -> Sequence[HabitRecord]:
        """
        获取习惯的所有打卡记录

        :param db: 数据库会话
        :param habit_id: 习惯 ID
        :return:
        """
        return await self.select_models_order(db, 'date', 'desc', habit_id=habit_id, deleted_at=None)

    async def get_select(
        self,
        habit_id: int | None,
        date_start: int | None,
        date_end: int | None,
        status: str | None,
        checkin_type: str | None,
    ) -> Select:
        """
        获取打卡记录列表查询表达式

        :param habit_id: 习惯 ID
        :param date_start: 开始日期时间戳
        :param date_end: 结束日期时间戳
        :param status: 状态
        :param checkin_type: 打卡类型
        :return:
        """
        filters = {'deleted_at': None}

        if habit_id is not None:
            filters['habit_id'] = habit_id
        if date_start is not None:
            filters['date__ge'] = date_start
        if date_end is not None:
            filters['date__le'] = date_end
        if status is not None:
            filters['status'] = status
        if checkin_type is not None:
            filters['checkin_type'] = checkin_type

        return await self.select_order('date', 'desc', **filters)

    async def create(self, db: AsyncSession, obj: CreateHabitRecordParam, user_id: int) -> HabitRecord:
        """
        创建打卡记录

        :param db: 数据库会话
        :param obj: 创建打卡记录参数
        :param user_id: 用户 ID
        :return:
        """
        dict_obj = obj.model_dump()
        dict_obj['created_by'] = user_id
        return await self.create_model(db, dict_obj, commit=False)

    async def update(self, db: AsyncSession, record_id: int, obj: UpdateHabitRecordParam, user_id: int) -> int:
        """
        更新打卡记录

        :param db: 数据库会话
        :param record_id: 记录 ID
        :param obj: 更新打卡记录参数
        :param user_id: 用户 ID
        :return:
        """
        dict_obj = obj.model_dump(exclude_unset=True)
        dict_obj['updated_by'] = user_id
        return await self.update_model(db, record_id, dict_obj)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        """
        批量软删除打卡记录

        :param db: 数据库会话
        :param pks: 记录 ID 列表
        :return:
        """
        import time
        deleted_at = int(time.time())
        count = 0
        for pk in pks:
            count += await self.update_model_by_column(db, {'deleted_at': deleted_at}, id=pk)
        return count


habit_dao: CRUDHabit = CRUDHabit(Habit)
habit_record_dao: CRUDHabitRecord = CRUDHabitRecord(HabitRecord)

