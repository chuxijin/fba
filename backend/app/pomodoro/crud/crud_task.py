#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.pomodoro.enums import PomodoroRepeatType, PomodoroTaskStatus
from backend.app.pomodoro.model.task import PomodoroTask


class CRUDPomodoroTask(CRUDPlus[PomodoroTask]):
    """番茄任务数据库操作类"""

    async def get_by_user(self, db: AsyncSession, user_id: int, task_id: int) -> PomodoroTask | None:
        """
        获取用户任务

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param task_id: 任务 ID
        :return:
        """
        return await self.select_model_by_column(db, id__eq=task_id, user_id__eq=user_id)

    async def get_select_by_user(
        self,
        user_id: int,
        status: PomodoroTaskStatus | None = None,
        keyword: str | None = None,
    ) -> Select:
        """
        获取用户任务列表查询

        :param user_id: 用户 ID
        :param status: 任务状态
        :param keyword: 标题关键词
        :return:
        """
        stmt = select(PomodoroTask).where(PomodoroTask.user_id == user_id)
        if status is not None:
            stmt = stmt.where(PomodoroTask.status == status.value)
        if keyword:
            keyword_like = f'%{keyword.strip()}%'
            stmt = stmt.where(PomodoroTask.title.ilike(keyword_like))

        return stmt.order_by(
            PomodoroTask.status.asc(),
            PomodoroTask.priority.desc(),
            PomodoroTask.due_at.asc().nullslast(),
            PomodoroTask.created_time.desc(),
        )

    async def get_by_repeat_key(self, db: AsyncSession, repeat_key: str) -> PomodoroTask | None:
        """
        通过重复实例唯一键获取任务

        :param db: 数据库会话
        :param repeat_key: 重复实例唯一键
        :return:
        """
        return await self.select_model_by_column(db, repeat_key__eq=repeat_key)

    async def get_repeat_templates(self, db: AsyncSession, user_id: int) -> list[PomodoroTask]:
        """
        获取重复任务模板

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = select(PomodoroTask).where(
            PomodoroTask.user_id == user_id,
            PomodoroTask.source_task_id.is_(None),
            PomodoroTask.repeat_type != PomodoroRepeatType.none.value,
            PomodoroTask.status != PomodoroTaskStatus.archived.value,
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_existing_schedule(
        self,
        db: AsyncSession,
        user_id: int,
        source_task_id: int,
        schedule_date: date,
    ) -> PomodoroTask | None:
        """
        获取已生成的计划任务

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param source_task_id: 来源任务 ID
        :param schedule_date: 计划日期
        :return:
        """
        return await self.select_model_by_column(
            db,
            user_id__eq=user_id,
            source_task_id__eq=source_task_id,
            schedule_date__eq=schedule_date,
        )


pomodoro_task_dao: CRUDPomodoroTask = CRUDPomodoroTask(PomodoroTask)
