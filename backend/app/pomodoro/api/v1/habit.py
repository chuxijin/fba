#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.pomodoro.enums import PomodoroHabitStatus
from backend.app.pomodoro.schema.habit import (
    CheckinPomodoroHabitParam,
    CreatePomodoroHabitParam,
    GetPomodoroHabitCheckinDetail,
    GetPomodoroHabitDetail,
    UpdatePomodoroHabitParam,
)
from backend.app.pomodoro.service.habit_service import pomodoro_habit_service
from backend.app.admin.service.tag_service import sys_tag_target_service
from backend.app.admin.service.cat_service import sys_cat_target_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(prefix='/pomodoro/habits', tags=['番茄习惯'], dependencies=[DependsJwtAuth])


@router.get(
    '',
    summary='获取番茄习惯列表',
    name='pomodoro_habit_list',
    response_model=ResponseSchemaModel[PageData[GetPomodoroHabitDetail]],
    dependencies=[DependsPagination],
)
async def get_pomodoro_habit_list(
    request: Request,
    db: CurrentSession,
    status: Annotated[PomodoroHabitStatus | None, Query(description='习惯状态')] = None,
) -> ResponseModel:
    """
    获取番茄习惯列表

    :param request: 请求对象
    :param db: 数据库会话
    :param status: 习惯状态
    :return:
    """
    data = await pomodoro_habit_service.get_list(db=db, user_id=request.user.id, status=status)
    return response_base.success(data=data)


@router.post(
    '',
    summary='创建番茄习惯',
    name='pomodoro_habit_create',
    response_model=ResponseSchemaModel[GetPomodoroHabitDetail],
)
async def create_pomodoro_habit(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreatePomodoroHabitParam,
) -> ResponseSchemaModel[GetPomodoroHabitDetail]:
    """
    创建番茄习惯

    :param request: 请求对象
    :param db: 数据库会话
    :param obj: 创建参数
    :return:
    """
    data = await pomodoro_habit_service.create(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.get(
    '/checkins/history',
    summary='获取番茄习惯打卡历史',
    name='pomodoro_habit_checkin_history',
    response_model=ResponseSchemaModel[PageData[GetPomodoroHabitCheckinDetail]],
    dependencies=[DependsPagination],
)
async def get_pomodoro_habit_checkin_history(
    request: Request,
    db: CurrentSession,
    year: Annotated[int | None, Query(description='年份')] = None,
    month: Annotated[int | None, Query(description='月份')] = None,
) -> ResponseModel:
    """
    获取番茄习惯打卡历史

    :param request: 请求对象
    :param db: 数据库会话
    :param year: 年份
    :param month: 月份
    :return:
    """
    data = await pomodoro_habit_service.get_checkin_history(
        db=db,
        user_id=request.user.id,
        year=year,
        month=month,
    )
    return response_base.success(data=data)


@router.get(
    '/{habit_id}',
    summary='获取番茄习惯详情',
    name='pomodoro_habit_get',
    response_model=ResponseSchemaModel[GetPomodoroHabitDetail],
)
async def get_pomodoro_habit(
    request: Request,
    db: CurrentSession,
    habit_id: Annotated[int, Path(description='习惯 ID')],
) -> ResponseSchemaModel[GetPomodoroHabitDetail]:
    """
    获取番茄习惯详情

    :param request: 请求对象
    :param db: 数据库会话
    :param habit_id: 习惯 ID
    :return:
    """
    habit = await pomodoro_habit_service.get(db=db, user_id=request.user.id, habit_id=habit_id)
    tags = await sys_tag_target_service.get_targets(db=db, target_type='pomodoro_habit', target_id=habit_id)
    categories = await sys_cat_target_service.get_targets(db=db, target_type='pomodoro_habit', target_id=habit_id)
    data = {
        **GetPomodoroHabitDetail.model_validate(habit).model_dump(),
        'tags': tags,
        'categories': categories,
    }
    return response_base.success(data=data)


@router.put(
    '/{habit_id}',
    summary='更新番茄习惯',
    name='pomodoro_habit_update',
    response_model=ResponseSchemaModel[GetPomodoroHabitDetail],
)
async def update_pomodoro_habit(
    request: Request,
    db: CurrentSessionTransaction,
    habit_id: Annotated[int, Path(description='习惯 ID')],
    obj: UpdatePomodoroHabitParam,
) -> ResponseSchemaModel[GetPomodoroHabitDetail]:
    """
    更新番茄习惯

    :param request: 请求对象
    :param db: 数据库会话
    :param habit_id: 习惯 ID
    :param obj: 更新参数
    :return:
    """
    data = await pomodoro_habit_service.update(db=db, user_id=request.user.id, habit_id=habit_id, obj=obj)
    return response_base.success(data=data)


@router.patch(
    '/{habit_id}/disable',
    summary='关闭番茄习惯',
    name='pomodoro_habit_disable',
    response_model=ResponseSchemaModel[GetPomodoroHabitDetail],
)
async def disable_pomodoro_habit(
    request: Request,
    db: CurrentSessionTransaction,
    habit_id: Annotated[int, Path(description='习惯 ID')],
) -> ResponseSchemaModel[GetPomodoroHabitDetail]:
    """
    关闭番茄习惯

    :param request: 请求对象
    :param db: 数据库会话
    :param habit_id: 习惯 ID
    :return:
    """
    data = await pomodoro_habit_service.disable(db=db, user_id=request.user.id, habit_id=habit_id)
    return response_base.success(data=data)


@router.post(
    '/{habit_id}/checkin',
    summary='番茄习惯打卡',
    name='pomodoro_habit_checkin',
    response_model=ResponseSchemaModel[GetPomodoroHabitCheckinDetail],
)
async def checkin_pomodoro_habit(
    request: Request,
    db: CurrentSessionTransaction,
    habit_id: Annotated[int, Path(description='习惯 ID')],
    obj: CheckinPomodoroHabitParam,
) -> ResponseSchemaModel[GetPomodoroHabitCheckinDetail]:
    """
    番茄习惯打卡

    :param request: 请求对象
    :param db: 数据库会话
    :param habit_id: 习惯 ID
    :param obj: 打卡参数
    :return:
    """
    data = await pomodoro_habit_service.checkin(db=db, user_id=request.user.id, habit_id=habit_id, obj=obj)
    return response_base.success(data=data)
