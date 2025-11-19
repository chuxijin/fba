#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.jia.model.reminders import Reminder
from backend.app.jia.schema.reminders import CreateReminderParam, UpdateReminderParam


class CRUDReminder(CRUDPlus[Reminder]):
    """提醒数据库操作类"""

    async def get(self, db: AsyncSession, reminder_id: int) -> Reminder | None:
        """
        获取提醒详情

        :param db: 数据库会话
        :param reminder_id: 提醒 ID
        :return:
        """
        return await self.select_model_by_column(db, id=reminder_id, deleted_at=None)

    async def get_by_server_id(self, db: AsyncSession, server_id: str) -> Reminder | None:
        """
        通过服务器 ID 获取提醒

        :param db: 数据库会话
        :param server_id: 服务器 ID
        :return:
        """
        return await self.select_model_by_column(db, server_id=server_id, deleted_at=None)

    async def get_select(
        self,
        scheduled_time_start: int | None,
        scheduled_time_end: int | None,
        is_completed: int | None,
        is_important: int | None,
        is_starred: int | None,
        is_pinned: int | None,
        priority: int | None,
        sync_status: str | None,
    ) -> Select:
        """
        获取提醒列表查询表达式

        :param scheduled_time_start: 开始计划时间
        :param scheduled_time_end: 结束计划时间
        :param is_completed: 是否完成
        :param is_important: 是否重要
        :param is_starred: 是否星标
        :param is_pinned: 是否置顶
        :param priority: 优先级
        :param sync_status: 同步状态
        :return:
        """
        filters = {'deleted_at': None}

        if scheduled_time_start is not None:
            filters['scheduled_time__ge'] = scheduled_time_start
        if scheduled_time_end is not None:
            filters['scheduled_time__le'] = scheduled_time_end
        if is_completed is not None:
            filters['is_completed'] = is_completed
        if is_important is not None:
            filters['is_important'] = is_important
        if is_starred is not None:
            filters['is_starred'] = is_starred
        if is_pinned is not None:
            filters['is_pinned'] = is_pinned
        if priority is not None:
            filters['priority'] = priority
        if sync_status is not None:
            filters['sync_status'] = sync_status

        return await self.select_order('scheduled_time', 'asc', **filters)

    async def get_all(self, db: AsyncSession, user_id: int) -> Sequence[Reminder]:
        """
        获取所有提醒

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await self.select_models_order(db, 'scheduled_time', 'asc', created_by=user_id, deleted_at=None)

    async def create(self, db: AsyncSession, obj: CreateReminderParam, user_id: int) -> Reminder:
        """
        创建提醒

        :param db: 数据库会话
        :param obj: 创建提醒参数
        :param user_id: 用户 ID
        :return:
        """
        dict_obj = obj.model_dump()
        dict_obj['created_by'] = user_id
        return await self.create_model(db, dict_obj, commit=False)

    async def update(self, db: AsyncSession, reminder_id: int, obj: UpdateReminderParam, user_id: int) -> int:
        """
        更新提醒

        :param db: 数据库会话
        :param reminder_id: 提醒 ID
        :param obj: 更新提醒参数
        :param user_id: 用户 ID
        :return:
        """
        dict_obj = obj.model_dump(exclude_unset=True)
        dict_obj['updated_by'] = user_id
        return await self.update_model(db, reminder_id, dict_obj)

    async def delete(self, db: AsyncSession, pks: list[int]) -> int:
        """
        批量软删除提醒

        :param db: 数据库会话
        :param pks: 提醒 ID 列表
        :return:
        """
        import time
        deleted_at = int(time.time())
        count = 0
        for pk in pks:
            count += await self.update_model_by_column(db, {'deleted_at': deleted_at}, id=pk)
        return count


reminder_dao: CRUDReminder = CRUDReminder(Reminder)

