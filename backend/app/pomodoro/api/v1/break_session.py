#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Request

from backend.app.pomodoro.schema.break_session import (
    FinishPomodoroBreakParam,
    GetPomodoroBreakSessionDetail,
    StartPomodoroBreakParam,
)
from backend.app.pomodoro.service.break_service import pomodoro_break_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(prefix='/pomodoro/breaks', tags=['番茄休息'], dependencies=[DependsJwtAuth])


@router.post(
    '/start',
    summary='开始番茄休息',
    name='pomodoro_break_start',
    response_model=ResponseSchemaModel[GetPomodoroBreakSessionDetail],
)
async def start_pomodoro_break(
    request: Request,
    db: CurrentSessionTransaction,
    obj: StartPomodoroBreakParam,
) -> ResponseSchemaModel[GetPomodoroBreakSessionDetail]:
    """
    开始番茄休息

    :param request: 请求对象
    :param db: 数据库会话
    :param obj: 开始参数
    :return:
    """
    data = await pomodoro_break_service.start(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.post(
    '/{break_id}/finish',
    summary='完成番茄休息',
    name='pomodoro_break_finish',
    response_model=ResponseSchemaModel[GetPomodoroBreakSessionDetail],
)
async def finish_pomodoro_break(
    request: Request,
    db: CurrentSessionTransaction,
    break_id: Annotated[int, Path(description='休息记录 ID')],
    obj: FinishPomodoroBreakParam,
) -> ResponseSchemaModel[GetPomodoroBreakSessionDetail]:
    """
    完成番茄休息

    :param request: 请求对象
    :param db: 数据库会话
    :param break_id: 休息记录 ID
    :param obj: 完成参数
    :return:
    """
    data = await pomodoro_break_service.finish(db=db, user_id=request.user.id, break_id=break_id, obj=obj)
    return response_base.success(data=data)


@router.post(
    '/{break_id}/cancel',
    summary='取消番茄休息',
    name='pomodoro_break_cancel',
    response_model=ResponseSchemaModel[GetPomodoroBreakSessionDetail],
)
async def cancel_pomodoro_break(
    request: Request,
    db: CurrentSessionTransaction,
    break_id: Annotated[int, Path(description='休息记录 ID')],
) -> ResponseSchemaModel[GetPomodoroBreakSessionDetail]:
    """
    取消番茄休息

    :param request: 请求对象
    :param db: 数据库会话
    :param break_id: 休息记录 ID
    :return:
    """
    data = await pomodoro_break_service.cancel(db=db, user_id=request.user.id, break_id=break_id)
    return response_base.success(data=data)


@router.get(
    '/current',
    summary='获取当前番茄休息',
    name='pomodoro_break_current',
    response_model=ResponseSchemaModel[GetPomodoroBreakSessionDetail | None],
)
async def get_current_pomodoro_break(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[GetPomodoroBreakSessionDetail | None]:
    """
    获取当前番茄休息

    :param request: 请求对象
    :param db: 数据库会话
    :return:
    """
    data = await pomodoro_break_service.get_current(db=db, user_id=request.user.id)
    return response_base.success(data=data)


@router.get(
    '/records',
    summary='获取番茄休息记录',
    name='pomodoro_break_records',
    response_model=ResponseSchemaModel[PageData[GetPomodoroBreakSessionDetail]],
    dependencies=[DependsPagination],
)
async def get_pomodoro_break_records(request: Request, db: CurrentSession) -> ResponseModel:
    """
    获取番茄休息记录

    :param request: 请求对象
    :param db: 数据库会话
    :return:
    """
    data = await pomodoro_break_service.get_records(db=db, user_id=request.user.id)
    return response_base.success(data=data)
