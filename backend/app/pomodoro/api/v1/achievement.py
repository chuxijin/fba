#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Request

from backend.app.pomodoro.schema.achievement import GetPomodoroAchievementList, GetPomodoroUserAchievementDetail
from backend.app.pomodoro.service.achievement_service import pomodoro_achievement_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSessionTransaction

router = APIRouter(prefix='/pomodoro/achievements', tags=['番茄成就'], dependencies=[DependsJwtAuth])


@router.get(
    '',
    summary='获取番茄成就列表',
    name='pomodoro_achievement_list',
    operation_id='pomodoroAchievementList',
    response_model=ResponseSchemaModel[GetPomodoroAchievementList],
)
async def get_pomodoro_achievement_list(
    request: Request,
    db: CurrentSessionTransaction,
) -> ResponseSchemaModel[GetPomodoroAchievementList]:
    """
    获取番茄成就列表

    :param request: 请求对象
    :param db: 数据库会话
    :return:
    """
    data = await pomodoro_achievement_service.get_list(db=db, user_id=request.user.id)
    return response_base.success(data=data)


@router.post(
    '/evaluate',
    summary='评估番茄成就',
    name='pomodoro_achievement_evaluate',
    operation_id='pomodoroAchievementEvaluate',
    response_model=ResponseSchemaModel[GetPomodoroAchievementList],
)
async def evaluate_pomodoro_achievement(
    request: Request,
    db: CurrentSessionTransaction,
) -> ResponseSchemaModel[GetPomodoroAchievementList]:
    """
    评估番茄成就

    :param request: 请求对象
    :param db: 数据库会话
    :return:
    """
    data = await pomodoro_achievement_service.evaluate(db=db, user_id=request.user.id)
    return response_base.success(data=data)


@router.post(
    '/{achievement_id}/claim',
    summary='领取番茄成就',
    name='pomodoro_achievement_claim',
    operation_id='pomodoroAchievementClaim',
    response_model=ResponseSchemaModel[GetPomodoroUserAchievementDetail],
)
async def claim_pomodoro_achievement(
    request: Request,
    db: CurrentSessionTransaction,
    achievement_id: Annotated[int, Path(description='用户成就 ID')],
) -> ResponseSchemaModel[GetPomodoroUserAchievementDetail]:
    """
    领取番茄成就

    :param request: 请求对象
    :param db: 数据库会话
    :param achievement_id: 用户成就 ID
    :return:
    """
    data = await pomodoro_achievement_service.claim(
        db=db,
        user_id=request.user.id,
        achievement_id=achievement_id,
    )
    return response_base.success(data=data)
