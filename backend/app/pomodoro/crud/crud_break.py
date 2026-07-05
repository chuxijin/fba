#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.pomodoro.enums import PomodoroBreakStatus
from backend.app.pomodoro.model.break_session import PomodoroBreakSession


class CRUDPomodoroBreak(CRUDPlus[PomodoroBreakSession]):
    """番茄休息数据库操作类"""

    async def get_by_user(self, db: AsyncSession, user_id: int, break_id: int) -> PomodoroBreakSession | None:
        """
        获取用户休息记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param break_id: 休息记录 ID
        :return:
        """
        return await self.select_model_by_column(db, id__eq=break_id, user_id__eq=user_id)

    async def get_current(self, db: AsyncSession, user_id: int) -> PomodoroBreakSession | None:
        """
        获取当前休息记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = (
            select(PomodoroBreakSession)
            .where(
                PomodoroBreakSession.user_id == user_id,
                PomodoroBreakSession.status == PomodoroBreakStatus.running.value,
            )
            .order_by(PomodoroBreakSession.created_time.desc())
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_select_by_user(self, user_id: int) -> Select:
        """
        获取用户休息记录查询

        :param user_id: 用户 ID
        :return:
        """
        return (
            select(PomodoroBreakSession)
            .where(PomodoroBreakSession.user_id == user_id)
            .order_by(PomodoroBreakSession.started_at.desc())
        )


pomodoro_break_dao: CRUDPomodoroBreak = CRUDPomodoroBreak(PomodoroBreakSession)
