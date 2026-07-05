#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Request
from fastapi import Query

from backend.app.pomodoro.schema.statistic import (
    GetPomodoroCalendarStatistic,
    GetPomodoroRangeStatistic,
    GetPomodoroSummaryStatistic,
    GetPomodoroTodayStatistic,
    PomodoroDistributionItem,
)
from backend.app.pomodoro.service.statistic_service import pomodoro_statistic_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter(prefix='/pomodoro/statistics', tags=['番茄统计'], dependencies=[DependsJwtAuth])


@router.get(
    '/summary',
    summary='获取番茄通用汇总统计',
    name='pomodoro_statistic_summary',
    response_model=ResponseSchemaModel[GetPomodoroSummaryStatistic],
)
async def get_pomodoro_summary_statistic(
    request: Request,
    db: CurrentSession,
    start_date: Annotated[date, Query(description='开始日期')],
    end_date: Annotated[date, Query(description='结束日期')],
    granularity: Annotated[str, Query(description='统计粒度(day 或 month)')] = 'day',
    distribution: Annotated[str, Query(description='分布维度(category 或 tag)')] = 'category',
) -> ResponseSchemaModel[GetPomodoroSummaryStatistic]:
    """
    获取番茄通用汇总统计

    :param request: 请求对象
    :param db: 数据库会话
    :param start_date: 开始日期
    :param end_date: 结束日期
    :param granularity: 统计粒度
    :param distribution: 分布维度
    :return:
    """
    data = await pomodoro_statistic_service.get_summary(
        db=db,
        user_id=request.user.id,
        start_date=start_date,
        end_date=end_date,
        granularity=granularity,
        distribution=distribution,
    )
    return response_base.success(data=data)


@router.get(
    '/today',
    summary='获取番茄今日统计',
    name='pomodoro_statistic_today',
    operation_id='pomodoroStatisticToday',
    response_model=ResponseSchemaModel[GetPomodoroTodayStatistic],
)
async def get_pomodoro_today_statistic(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[GetPomodoroTodayStatistic]:
    """
    获取番茄今日统计

    :param request: 请求对象
    :param db: 数据库会话
    :return:
    """
    data = await pomodoro_statistic_service.get_today(db=db, user_id=request.user.id)
    return response_base.success(data=data)


@router.get(
    '/today/distribution',
    summary='获取番茄今日专注分布',
    name='pomodoro_statistic_today_distribution',
    response_model=ResponseSchemaModel[list[PomodoroDistributionItem]],
)
async def get_pomodoro_today_distribution(
    request: Request,
    db: CurrentSession,
    dimension: Annotated[str, Query(description='维度(category 或 tag)')] = 'category',
) -> ResponseSchemaModel[list[PomodoroDistributionItem]]:
    """
    获取番茄今日专注分布

    :param request: 请求对象
    :param db: 数据库会话
    :param dimension: 维度
    :return:
    """
    data = await pomodoro_statistic_service.get_today_distribution(
        db=db,
        user_id=request.user.id,
        dimension=dimension,
    )
    return response_base.success(data=data)


@router.get(
    '/total',
    summary='获取番茄累计统计',
    name='pomodoro_statistic_total',
)
async def get_pomodoro_total_statistic(
    request: Request,
    db: CurrentSession,
):
    """
    获取番茄累计统计

    :param request: 请求对象
    :param db: 数据库会话
    :return:
    """
    data = await pomodoro_statistic_service.get_total(db=db, user_id=request.user.id)
    return response_base.success(data=data)


@router.get(
    '/weekly',
    summary='获取番茄周统计',
    name='pomodoro_statistic_weekly',
    response_model=ResponseSchemaModel[GetPomodoroRangeStatistic],
)
async def get_pomodoro_weekly_statistic(
    request: Request,
    db: CurrentSession,
    base_date: Annotated[date | None, Query(description='基准日期')] = None,
) -> ResponseSchemaModel[GetPomodoroRangeStatistic]:
    """
    获取番茄周统计

    :param request: 请求对象
    :param db: 数据库会话
    :param base_date: 基准日期
    :return:
    """
    data = await pomodoro_statistic_service.get_weekly(db=db, user_id=request.user.id, base_date=base_date)
    return response_base.success(data=data)


@router.get(
    '/monthly',
    summary='获取番茄月统计',
    name='pomodoro_statistic_monthly',
    response_model=ResponseSchemaModel[GetPomodoroRangeStatistic],
)
async def get_pomodoro_monthly_statistic(
    request: Request,
    db: CurrentSession,
    year: Annotated[int | None, Query(description='年份')] = None,
    month: Annotated[int | None, Query(ge=1, le=12, description='月份')] = None,
) -> ResponseSchemaModel[GetPomodoroRangeStatistic]:
    """
    获取番茄月统计

    :param request: 请求对象
    :param db: 数据库会话
    :param year: 年份
    :param month: 月份
    :return:
    """
    data = await pomodoro_statistic_service.get_monthly(
        db=db,
        user_id=request.user.id,
        year=year,
        month=month,
    )
    return response_base.success(data=data)


@router.get(
    '/calendar',
    summary='获取番茄日历统计',
    name='pomodoro_statistic_calendar',
    response_model=ResponseSchemaModel[GetPomodoroCalendarStatistic],
)
async def get_pomodoro_calendar_statistic(
    request: Request,
    db: CurrentSession,
    year: Annotated[int, Query(description='年份')],
    month: Annotated[int, Query(ge=1, le=12, description='月份')],
) -> ResponseSchemaModel[GetPomodoroCalendarStatistic]:
    """
    获取番茄日历统计

    :param request: 请求对象
    :param db: 数据库会话
    :param year: 年份
    :param month: 月份
    :return:
    """
    data = await pomodoro_statistic_service.get_calendar(
        db=db,
        user_id=request.user.id,
        year=year,
        month=month,
    )
    return response_base.success(data=data)
