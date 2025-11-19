#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.jia.crud.crud_reminders import reminder_dao
from backend.app.jia.model.reminders import Reminder
from backend.app.jia.schema.reminders import CreateReminderParam, UpdateReminderParam
from backend.common.exception import errors


class ReminderService:
    """提醒服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, pk: int) -> Reminder:
        """
        获取提醒详情

        :param db: 数据库会话
        :param pk: 提醒 ID
        :return:
        """
        reminder = await reminder_dao.get(db, pk)
        if not reminder:
            raise errors.NotFoundError(msg='提醒不存在')
        return reminder

    @staticmethod
    async def get_list(
        *,
        db: AsyncSession,
        scheduled_time_start: int | None = None,
        scheduled_time_end: int | None = None,
        is_completed: int | None = None,
        is_important: int | None = None,
        is_starred: int | None = None,
        is_pinned: int | None = None,
        priority: int | None = None,
        sync_status: str | None = None,
    ) -> list[Reminder]:
        """
        获取提醒列表

        :param db: 数据库会话
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
        select_stmt = await reminder_dao.get_select(
            scheduled_time_start,
            scheduled_time_end,
            is_completed,
            is_important,
            is_starred,
            is_pinned,
            priority,
            sync_status,
        )
        reminders = await db.execute(select_stmt)
        return list(reminders.scalars().all())

    @staticmethod
    async def get_all(*, db: AsyncSession, user_id: int) -> list[Reminder]:
        """
        获取所有提醒

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return list(await reminder_dao.get_all(db, user_id))

    @staticmethod
    async def create(*, db: AsyncSession, obj: CreateReminderParam, user_id: int) -> None:
        """
        创建提醒

        :param db: 数据库会话
        :param obj: 创建提醒参数
        :param user_id: 用户 ID
        :return:
        """
        await reminder_dao.create(db, obj, user_id)

    @staticmethod
    async def update(*, db: AsyncSession, pk: int, obj: UpdateReminderParam, user_id: int) -> int:
        """
        更新提醒

        :param db: 数据库会话
        :param pk: 提醒 ID
        :param obj: 更新提醒参数
        :param user_id: 用户 ID
        :return:
        """
        reminder = await reminder_dao.get(db, pk)
        if not reminder:
            raise errors.NotFoundError(msg='提醒不存在')
        count = await reminder_dao.update(db, pk, obj, user_id)
        return count

    @staticmethod
    async def delete(*, db: AsyncSession, pks: list[int]) -> int:
        """
        批量删除提醒

        :param db: 数据库会话
        :param pks: 提醒 ID 列表
        :return:
        """
        count = await reminder_dao.delete(db, pks)
        return count


reminder_service: ReminderService = ReminderService()

