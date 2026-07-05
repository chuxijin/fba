#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.pomodoro.schema.focus import (
    FinishPomodoroFocusParam,
    GetPomodoroFocusRecordItem,
    GetPomodoroFocusSessionDetail,
    StartPomodoroFocusParam,
)
from backend.app.pomodoro.service.focus_service import pomodoro_focus_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(prefix='/pomodoro/focus', tags=['番茄专注'], dependencies=[DependsJwtAuth])


@router.post(
    '/start',
    summary='开始番茄专注',
    name='pomodoro_focus_start',
    operation_id='pomodoroFocusStart',
    response_model=ResponseSchemaModel[GetPomodoroFocusSessionDetail],
)
async def start_pomodoro_focus(
    request: Request,
    db: CurrentSessionTransaction,
    obj: StartPomodoroFocusParam,
) -> ResponseSchemaModel[GetPomodoroFocusSessionDetail]:
    """
    开始番茄专注

    :param request: 请求对象
    :param db: 数据库会话
    :param obj: 开始参数
    :return:
    """
    data = await pomodoro_focus_service.start(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.post(
    '/{session_id}/pause',
    summary='暂停番茄专注',
    name='pomodoro_focus_pause',
    operation_id='pomodoroFocusPause',
    response_model=ResponseSchemaModel[GetPomodoroFocusSessionDetail],
)
async def pause_pomodoro_focus(
    request: Request,
    db: CurrentSessionTransaction,
    session_id: Annotated[int, Path(description='专注记录 ID')],
) -> ResponseSchemaModel[GetPomodoroFocusSessionDetail]:
    """
    暂停番茄专注

    :param request: 请求对象
    :param db: 数据库会话
    :param session_id: 专注记录 ID
    :return:
    """
    data = await pomodoro_focus_service.pause(db=db, user_id=request.user.id, session_id=session_id)
    return response_base.success(data=data)


@router.post(
    '/{session_id}/resume',
    summary='继续番茄专注',
    name='pomodoro_focus_resume',
    operation_id='pomodoroFocusResume',
    response_model=ResponseSchemaModel[GetPomodoroFocusSessionDetail],
)
async def resume_pomodoro_focus(
    request: Request,
    db: CurrentSessionTransaction,
    session_id: Annotated[int, Path(description='专注记录 ID')],
) -> ResponseSchemaModel[GetPomodoroFocusSessionDetail]:
    """
    继续番茄专注

    :param request: 请求对象
    :param db: 数据库会话
    :param session_id: 专注记录 ID
    :return:
    """
    data = await pomodoro_focus_service.resume(db=db, user_id=request.user.id, session_id=session_id)
    return response_base.success(data=data)


@router.post(
    '/{session_id}/finish',
    summary='完成番茄专注',
    name='pomodoro_focus_finish',
    operation_id='pomodoroFocusFinish',
    response_model=ResponseSchemaModel[GetPomodoroFocusSessionDetail],
)
async def finish_pomodoro_focus(
    request: Request,
    db: CurrentSessionTransaction,
    session_id: Annotated[int, Path(description='专注记录 ID')],
    obj: FinishPomodoroFocusParam,
) -> ResponseSchemaModel[GetPomodoroFocusSessionDetail]:
    """
    完成番茄专注

    :param request: 请求对象
    :param db: 数据库会话
    :param session_id: 专注记录 ID
    :param obj: 完成参数
    :return:
    """
    data = await pomodoro_focus_service.finish(db=db, user_id=request.user.id, session_id=session_id, obj=obj)
    return response_base.success(data=data)


@router.post(
    '/{session_id}/cancel',
    summary='取消番茄专注',
    name='pomodoro_focus_cancel',
    operation_id='pomodoroFocusCancel',
    response_model=ResponseSchemaModel[GetPomodoroFocusSessionDetail],
)
async def cancel_pomodoro_focus(
    request: Request,
    db: CurrentSessionTransaction,
    session_id: Annotated[int, Path(description='专注记录 ID')],
) -> ResponseSchemaModel[GetPomodoroFocusSessionDetail]:
    """
    取消番茄专注

    :param request: 请求对象
    :param db: 数据库会话
    :param session_id: 专注记录 ID
    :return:
    """
    data = await pomodoro_focus_service.cancel(db=db, user_id=request.user.id, session_id=session_id)
    return response_base.success(data=data)


@router.get(
    '/current',
    summary='获取当前番茄专注',
    name='pomodoro_focus_current',
    operation_id='pomodoroFocusCurrent',
    response_model=ResponseSchemaModel[GetPomodoroFocusSessionDetail | None],
)
async def get_current_pomodoro_focus(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[GetPomodoroFocusSessionDetail | None]:
    """
    获取当前番茄专注

    :param request: 请求对象
    :param db: 数据库会话
    :return:
    """
    data = await pomodoro_focus_service.get_current(db=db, user_id=request.user.id)
    return response_base.success(data=data)


@router.get(
    '/records',
    summary='获取番茄专注记录',
    name='pomodoro_focus_records',
    operation_id='pomodoroFocusRecords',
    response_model=ResponseSchemaModel[PageData[GetPomodoroFocusRecordItem]],
    dependencies=[DependsPagination],
)
async def get_pomodoro_focus_records(
    request: Request,
    db: CurrentSession,
    start_at: Annotated[datetime | None, Query(description='开始时间')] = None,
    end_at: Annotated[datetime | None, Query(description='结束时间')] = None,
    task_id: Annotated[int | None, Query(description='任务 ID')] = None,
) -> ResponseModel:
    """
    获取番茄专注记录

    :param request: 请求对象
    :param db: 数据库会话
    :param start_at: 开始时间
    :param end_at: 结束时间
    :param task_id: 任务 ID
    :return:
    """
    data = await pomodoro_focus_service.get_records(
        db=db,
        user_id=request.user.id,
        start_at=start_at,
        end_at=end_at,
        task_id=task_id,
    )
    return response_base.success(data=data)
