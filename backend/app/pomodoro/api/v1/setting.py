#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter, Request

from backend.app.pomodoro.schema.setting import GetPomodoroUserSettingDetail, UpdatePomodoroUserSettingParam
from backend.app.pomodoro.service.setting_service import pomodoro_setting_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(prefix='/pomodoro/settings', tags=['番茄设置'], dependencies=[DependsJwtAuth])


@router.get(
    '',
    summary='获取番茄设置',
    name='pomodoro_setting_get',
    response_model=ResponseSchemaModel[GetPomodoroUserSettingDetail],
)
async def get_pomodoro_setting(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[GetPomodoroUserSettingDetail]:
    """
    获取番茄设置

    :param request: 请求对象
    :param db: 数据库会话
    :return:
    """
    data = await pomodoro_setting_service.get_or_create(db=db, user_id=request.user.id)
    return response_base.success(data=data)


@router.put(
    '',
    summary='更新番茄设置',
    name='pomodoro_setting_update',
    response_model=ResponseSchemaModel[GetPomodoroUserSettingDetail],
)
async def update_pomodoro_setting(
    request: Request,
    db: CurrentSessionTransaction,
    obj: UpdatePomodoroUserSettingParam,
) -> ResponseSchemaModel[GetPomodoroUserSettingDetail]:
    """
    更新番茄设置

    :param request: 请求对象
    :param db: 数据库会话
    :param obj: 更新参数
    :return:
    """
    data = await pomodoro_setting_service.update(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)
