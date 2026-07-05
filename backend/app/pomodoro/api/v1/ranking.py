#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Query, Request

from backend.app.pomodoro.enums import PomodoroRankingPeriod, PomodoroRankingScope
from backend.app.pomodoro.schema.ranking import GetPomodoroRankingDetail
from backend.app.pomodoro.service.ranking_service import pomodoro_ranking_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter(prefix='/pomodoro/rankings', tags=['番茄排行榜'], dependencies=[DependsJwtAuth])


@router.get(
    '/today',
    summary='获取番茄今日专注榜',
    name='pomodoro_ranking_today',
    operation_id='pomodoroRankingToday',
    response_model=ResponseSchemaModel[GetPomodoroRankingDetail],
)
async def get_pomodoro_today_ranking(
    request: Request,
    db: CurrentSession,
    scope: Annotated[PomodoroRankingScope, Query(description='榜单范围')] = PomodoroRankingScope.global_,
    limit: Annotated[int, Query(ge=1, le=100, description='返回数量')] = 50,
) -> ResponseSchemaModel[GetPomodoroRankingDetail]:
    """
    获取番茄今日专注榜

    :param request: 请求对象
    :param db: 数据库会话
    :param scope: 榜单范围
    :param limit: 返回数量
    :return:
    """
    data = await pomodoro_ranking_service.get_ranking(
        db=db,
        user_id=request.user.id,
        period=PomodoroRankingPeriod.today,
        scope=scope,
        limit=limit,
    )
    return response_base.success(data=data)


@router.get(
    '/weekly',
    summary='获取番茄本周专注榜',
    name='pomodoro_ranking_weekly',
    operation_id='pomodoroRankingWeekly',
    response_model=ResponseSchemaModel[GetPomodoroRankingDetail],
)
async def get_pomodoro_weekly_ranking(
    request: Request,
    db: CurrentSession,
    scope: Annotated[PomodoroRankingScope, Query(description='榜单范围')] = PomodoroRankingScope.global_,
    limit: Annotated[int, Query(ge=1, le=100, description='返回数量')] = 50,
) -> ResponseSchemaModel[GetPomodoroRankingDetail]:
    """
    获取番茄本周专注榜

    :param request: 请求对象
    :param db: 数据库会话
    :param scope: 榜单范围
    :param limit: 返回数量
    :return:
    """
    data = await pomodoro_ranking_service.get_ranking(
        db=db,
        user_id=request.user.id,
        period=PomodoroRankingPeriod.weekly,
        scope=scope,
        limit=limit,
    )
    return response_base.success(data=data)
