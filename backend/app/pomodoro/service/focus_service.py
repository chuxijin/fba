#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.pomodoro.crud.crud_focus import pomodoro_focus_dao
from backend.app.pomodoro.crud.crud_task import pomodoro_task_dao
from backend.app.pomodoro.enums import PomodoroFocusStatus, PomodoroTaskStatus
from backend.app.pomodoro.model.focus import PomodoroFocusSession
from backend.app.pomodoro.schema.focus import CreatePomodoroFocusInternal, FinishPomodoroFocusParam, StartPomodoroFocusParam
from backend.common.exception import errors
from backend.common.pagination import paging_data
from backend.utils.timezone import timezone


class PomodoroFocusService:
    """番茄专注服务类"""

    @staticmethod
    async def get(*, db: AsyncSession, user_id: int, session_id: int) -> PomodoroFocusSession:
        """
        获取用户专注记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param session_id: 专注记录 ID
        :return:
        """
        session = await pomodoro_focus_dao.get_by_user(db, user_id, session_id)
        if not session:
            raise errors.NotFoundError(msg='专注记录不存在或无权访问')
        return session

    @staticmethod
    async def get_current(*, db: AsyncSession, user_id: int) -> PomodoroFocusSession | None:
        """
        获取当前专注

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await pomodoro_focus_dao.get_current(db, user_id)

    @staticmethod
    async def get_records(
        *,
        db: AsyncSession,
        user_id: int,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        task_id: int | None = None,
    ) -> dict:
        """
        获取专注记录分页列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param start_at: 开始时间
        :param end_at: 结束时间
        :param task_id: 任务 ID
        :return:
        """
        stmt = await pomodoro_focus_dao.get_select_by_user(
            user_id=user_id,
            start_at=start_at,
            end_at=end_at,
            task_id=task_id,
        )
        return await paging_data(db, stmt)

    @staticmethod
    async def start(*, db: AsyncSession, user_id: int, obj: StartPomodoroFocusParam) -> PomodoroFocusSession:
        """
        开始专注

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param obj: 开始参数
        :return:
        """
        current_session = await pomodoro_focus_dao.get_current(db, user_id)
        if current_session:
            raise errors.ConflictError(msg='请先完成或取消当前专注')

        if obj.task_id is not None:
            task = await pomodoro_task_dao.get_by_user(db, user_id, obj.task_id)
            if not task:
                raise errors.NotFoundError(msg='任务不存在或无权访问')
            if task.status == PomodoroTaskStatus.pending.value:
                await pomodoro_task_dao.update_model(
                    db,
                    task.id,
                    {'status': PomodoroTaskStatus.doing.value},
                    commit=False,
                )

        data = CreatePomodoroFocusInternal(
            user_id=user_id,
            started_at=timezone.now(),
            **obj.model_dump(mode='json'),
        )
        session = await pomodoro_focus_dao.create_model(db, data, commit=False)
        await db.flush()
        await db.refresh(session)
        return session

    @staticmethod
    async def pause(*, db: AsyncSession, user_id: int, session_id: int) -> PomodoroFocusSession:
        """
        暂停专注

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param session_id: 专注记录 ID
        :return:
        """
        session = await PomodoroFocusService.get(db=db, user_id=user_id, session_id=session_id)
        if session.status != PomodoroFocusStatus.running.value:
            raise errors.ForbiddenError(msg='当前专注状态不能暂停')

        await pomodoro_focus_dao.update_model(
            db,
            session.id,
            {
                'status': PomodoroFocusStatus.paused.value,
                'paused_at': timezone.now(),
            },
            commit=False,
        )
        await db.flush()
        await db.refresh(session)
        return session

    @staticmethod
    async def resume(*, db: AsyncSession, user_id: int, session_id: int) -> PomodoroFocusSession:
        """
        继续专注

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param session_id: 专注记录 ID
        :return:
        """
        session = await PomodoroFocusService.get(db=db, user_id=user_id, session_id=session_id)
        if session.status != PomodoroFocusStatus.paused.value:
            raise errors.ForbiddenError(msg='当前专注状态不能继续')

        now = timezone.now()
        paused_seconds = session.paused_seconds
        if session.paused_at:
            paused_seconds += max(0, int((now - session.paused_at).total_seconds()))

        await pomodoro_focus_dao.update_model(
            db,
            session.id,
            {
                'status': PomodoroFocusStatus.running.value,
                'paused_seconds': paused_seconds,
                'paused_at': None,
            },
            commit=False,
        )
        await db.flush()
        await db.refresh(session)
        return session

    @staticmethod
    async def finish(
        *,
        db: AsyncSession,
        user_id: int,
        session_id: int,
        obj: FinishPomodoroFocusParam,
    ) -> PomodoroFocusSession:
        """
        完成专注

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param session_id: 专注记录 ID
        :param obj: 完成参数
        :return:
        """
        session = await PomodoroFocusService.get(db=db, user_id=user_id, session_id=session_id)
        if session.status not in {PomodoroFocusStatus.running.value, PomodoroFocusStatus.paused.value}:
            raise errors.ForbiddenError(msg='当前专注状态不能完成')

        now = timezone.now()
        paused_seconds = obj.paused_seconds
        if session.status == PomodoroFocusStatus.paused.value and session.paused_at:
            paused_seconds += max(0, int((now - session.paused_at).total_seconds()))

        server_elapsed_seconds = max(0, int((now - session.started_at).total_seconds()))
        max_focus_seconds = max(0, server_elapsed_seconds - paused_seconds)
        focused_seconds = min(obj.focused_seconds, max_focus_seconds)

        await pomodoro_focus_dao.update_model(
            db,
            session.id,
            {
                'status': PomodoroFocusStatus.completed.value,
                'focused_seconds': focused_seconds,
                'paused_seconds': paused_seconds,
                'interrupt_count': obj.interrupt_count,
                'ended_at': now,
                'paused_at': None,
                'remark': obj.remark,
            },
            commit=False,
        )
        await db.flush()
        await db.refresh(session)
        return session

    @staticmethod
    async def cancel(*, db: AsyncSession, user_id: int, session_id: int) -> PomodoroFocusSession:
        """
        取消专注

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param session_id: 专注记录 ID
        :return:
        """
        session = await PomodoroFocusService.get(db=db, user_id=user_id, session_id=session_id)
        if session.status not in {PomodoroFocusStatus.running.value, PomodoroFocusStatus.paused.value}:
            raise errors.ForbiddenError(msg='当前专注状态不能取消')

        await pomodoro_focus_dao.update_model(
            db,
            session.id,
            {
                'status': PomodoroFocusStatus.canceled.value,
                'ended_at': timezone.now(),
                'paused_at': None,
            },
            commit=False,
        )
        await db.flush()
        await db.refresh(session)
        return session


pomodoro_focus_service: PomodoroFocusService = PomodoroFocusService()
