#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.pomodoro.crud.crud_break import pomodoro_break_dao
from backend.app.pomodoro.crud.crud_focus import pomodoro_focus_dao
from backend.app.pomodoro.enums import PomodoroBreakStatus, PomodoroBreakType
from backend.app.pomodoro.model.break_session import PomodoroBreakSession
from backend.app.pomodoro.schema.break_session import CreatePomodoroBreakInternal, FinishPomodoroBreakParam, StartPomodoroBreakParam
from backend.app.pomodoro.service.setting_service import pomodoro_setting_service
from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.utils.timezone import timezone


class PomodoroBreakService:
    """番茄休息服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, user_id: int, break_id: int) -> PomodoroBreakSession:
        """
        获取休息记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param break_id: 休息记录 ID
        :return:
        """
        break_session = await pomodoro_break_dao.get_by_user(db, user_id, break_id)
        if not break_session:
            raise errors.NotFoundError(msg='休息记录不存在或无权访问')
        return break_session

    @staticmethod
    async def get_current(*, db: AsyncSession, user_id: int) -> PomodoroBreakSession | None:
        """
        获取当前休息

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await pomodoro_break_dao.get_current(db, user_id)

    @staticmethod
    async def get_records(*, db: AsyncSession, user_id: int) -> dict:
        """
        获取休息记录分页列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = await pomodoro_break_dao.get_select_by_user(user_id)
        return await paging_data(db, stmt)

    @staticmethod
    async def start(*, db: AsyncSession, user_id: int, obj: StartPomodoroBreakParam) -> PomodoroBreakSession:
        """
        开始休息

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param obj: 开始参数
        :return:
        """
        current_break = await pomodoro_break_dao.get_current(db, user_id)
        if current_break:
            raise errors.ConflictError(msg='请先完成或取消当前休息')

        if obj.focus_session_id is not None:
            focus_session = await pomodoro_focus_dao.get_by_user(db, user_id, obj.focus_session_id)
            if not focus_session:
                raise errors.NotFoundError(msg='专注记录不存在或无权访问')

        planned_minutes = obj.planned_minutes
        if planned_minutes is None:
            setting = await pomodoro_setting_service.get_or_create(db=db, user_id=user_id)
            if obj.break_type == PomodoroBreakType.long:
                planned_minutes = setting.long_break_minutes
            else:
                planned_minutes = setting.short_break_minutes

        data = CreatePomodoroBreakInternal(
            user_id=user_id,
            focus_session_id=obj.focus_session_id,
            break_type=obj.break_type,
            planned_minutes=planned_minutes,
            started_at=timezone.now(),
        )
        break_session = await pomodoro_break_dao.create_model(db, data, commit=False)
        await db.flush()
        await db.refresh(break_session)
        return break_session

    @staticmethod
    async def finish(
        *,
        db: AsyncSession,
        user_id: int,
        break_id: int,
        obj: FinishPomodoroBreakParam,
    ) -> PomodoroBreakSession:
        """
        完成休息

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param break_id: 休息记录 ID
        :param obj: 完成参数
        :return:
        """
        break_session = await PomodoroBreakService.get(db=db, user_id=user_id, break_id=break_id)
        if break_session.status != PomodoroBreakStatus.running.value:
            raise errors.ForbiddenError(msg='当前休息状态不能完成')

        now = timezone.now()
        max_break_seconds = max(0, int((now - break_session.started_at).total_seconds()))
        break_seconds = min(obj.break_seconds, max_break_seconds)
        await pomodoro_break_dao.update_model(
            db,
            break_session.id,
            {
                'status': PomodoroBreakStatus.completed.value,
                'break_seconds': break_seconds,
                'ended_at': now,
            },
            commit=False,
        )
        await db.flush()
        await db.refresh(break_session)
        return break_session

    @staticmethod
    async def cancel(*, db: AsyncSession, user_id: int, break_id: int) -> PomodoroBreakSession:
        """
        取消休息

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param break_id: 休息记录 ID
        :return:
        """
        break_session = await PomodoroBreakService.get(db=db, user_id=user_id, break_id=break_id)
        if break_session.status != PomodoroBreakStatus.running.value:
            raise errors.ForbiddenError(msg='当前休息状态不能取消')

        await pomodoro_break_dao.update_model(
            db,
            break_session.id,
            {
                'status': PomodoroBreakStatus.canceled.value,
                'ended_at': timezone.now(),
            },
            commit=False,
        )
        await db.flush()
        await db.refresh(break_session)
        return break_session


pomodoro_break_service: PomodoroBreakService = PomodoroBreakService()
