#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.pomodoro.enums import PomodoroFocusStatus
from backend.app.pomodoro.model.focus import PomodoroFocusSession


class CRUDPomodoroFocus(CRUDPlus[PomodoroFocusSession]):
    """番茄专注数据库操作类"""

    async def get_by_user(self, db: AsyncSession, user_id: int, session_id: int) -> PomodoroFocusSession | None:
        """
        获取用户专注记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param session_id: 专注记录 ID
        :return:
        """
        return await self.select_model_by_column(db, id__eq=session_id, user_id__eq=user_id)

    async def get_current(self, db: AsyncSession, user_id: int) -> PomodoroFocusSession | None:
        """
        获取当前未结束专注

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = (
            select(PomodoroFocusSession)
            .where(
                PomodoroFocusSession.user_id == user_id,
                PomodoroFocusSession.status.in_(
                    [PomodoroFocusStatus.running.value, PomodoroFocusStatus.paused.value]
                ),
            )
            .order_by(PomodoroFocusSession.created_time.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_select_by_user(
        self,
        user_id: int,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        task_id: int | None = None,
    ) -> Select:
        """
        获取用户专注记录查询

        :param user_id: 用户 ID
        :param start_at: 开始时间
        :param end_at: 结束时间
        :param task_id: 任务 ID
        :return:
        """
        stmt = select(PomodoroFocusSession).where(PomodoroFocusSession.user_id == user_id)
        if start_at is not None:
            stmt = stmt.where(PomodoroFocusSession.started_at >= start_at)
        if end_at is not None:
            stmt = stmt.where(PomodoroFocusSession.started_at <= end_at)
        if task_id is not None:
            stmt = stmt.where(PomodoroFocusSession.task_id == task_id)

        return stmt.order_by(PomodoroFocusSession.started_at.desc())


pomodoro_focus_dao: CRUDPomodoroFocus = CRUDPomodoroFocus(PomodoroFocusSession)
