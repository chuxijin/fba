#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Query, Request

from backend.app.question_bank.schema.home import (
    CheckInCalendarData,
    CheckInParam,
    CheckInResult,
    HomeDashboardData,
    RankListData,
)
from backend.app.question_bank.service.check_in_service import check_in_service
from backend.app.question_bank.service.home_service import home_service
from backend.app.question_bank.service.rank_service import rank_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction
from backend.utils.timezone import timezone

router = APIRouter()


@router.get('/dashboard', summary='获取首页Dashboard数据', name='home_dashboard', dependencies=[DependsJwtAuth])
async def get_home_dashboard(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[HomeDashboardData]:
    """
    👤 客户端首页 - 获取Dashboard聚合数据

    一次性返回首页所需的所有统计数据：
    - 打卡信息（连续打卡天数、今日是否已打卡）
    - 本周刷题统计
    - 排名信息（击败用户百分比）
    - 累计做题数据
    """
    dashboard_data = await home_service.get_dashboard_data(db=db, user_id=request.user.id)
    return response_base.success(data=dashboard_data)


@router.post('/check-in', summary='用户打卡', name='home_check_in', dependencies=[DependsJwtAuth])
async def check_in(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CheckInParam,
) -> ResponseSchemaModel[CheckInResult]:
    """
    👤 客户端首页 - 用户打卡

    在用户完成一定数量的做题后触发打卡
    """
    data = await check_in_service.check_in(
        db=db,
        user_id=request.user.id,
        practice_count=obj.practice_count,
        practice_duration=obj.practice_duration,
    )
    return response_base.success(data=data)


@router.get('/check-in-calendar', summary='获取打卡日历', name='home_check_in_calendar', dependencies=[DependsJwtAuth])
async def get_check_in_calendar(
    request: Request,
    db: CurrentSession,
    year: Annotated[int | None, Query(description='年份（默认当前年）')] = None,
    month: Annotated[int | None, Query(description='月份（默认当前月，1-12）')] = None,
) -> ResponseSchemaModel[CheckInCalendarData]:
    """
    👤 客户端首页 - 获取打卡日历

    获取指定月份的打卡日历数据，包括每天的打卡状态和做题数
    """
    today = timezone.now().date()
    year = year or today.year
    month = month or today.month

    calendar_data = await check_in_service.get_check_in_calendar(
        db=db,
        user_id=request.user.id,
        year=year,
        month=month,
    )
    return response_base.success(data=calendar_data)


@router.get('/rank', summary='获取排行榜列表', name='home_rank_list', dependencies=[DependsJwtAuth])
async def get_rank_list(
    request: Request,
    db: CurrentSession,
    rank_type: Annotated[
        str,
        Query(description='排行榜类型（practice_count: 刷题数量, accuracy_rate: 正确率, streak_days: 坚持天数）'),
    ] = 'practice_count',
    limit: Annotated[int, Query(ge=1, le=500, description='返回数量（默认 100，最大 500）')] = 100,
) -> ResponseSchemaModel[RankListData]:
    """
    👤 客户端首页 - 获取排行榜列表

    获取排行榜数据，支持三种排行榜类型：
    - practice_count: 刷题数量排行榜
    - accuracy_rate: 正确率排行榜（要求至少做过 10 题）
    - streak_days: 坚持天数排行榜（连续打卡天数）
    """
    rank_data = await rank_service.get_rank_list(
        db=db,
        rank_type=rank_type,
        current_user_id=request.user.id,
        limit=limit,
    )
    return response_base.success(data=rank_data)
