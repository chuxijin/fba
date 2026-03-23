#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""首页接口"""
from datetime import date

from fastapi import APIRouter, Query, Request

from backend.app.question_bank.schema.home import (
    CheckInCalendarData,
    CheckInParam,
    HomeDashboardData,
    RankListData,
)
from backend.common.security.jwt import DependsJwtAuth
from backend.app.question_bank.service.check_in_service import check_in_service
from backend.app.question_bank.service.home_service import home_service
from backend.app.question_bank.service.rank_service import rank_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/dashboard', summary='获取首页Dashboard数据', name='home_dashboard')
async def get_home_dashboard(
    db: CurrentSession,
    request: Request, _token: str = DependsJwtAuth,
) -> ResponseSchemaModel[HomeDashboardData]:
    """
    👤 客户端首页 - 获取Dashboard聚合数据

    一次性返回首页所需的所有统计数据：
    - 打卡信息（连续打卡天数、今日是否已打卡）
    - 本周刷题统计
    - 排名信息（击败用户百分比）
    - 累计做题数据

    数据更新策略：
    - 实时数据：今日打卡、今日做题（每次请求计算）
    - 准实时数据：本周统计、累计数据（可缓存5分钟）
    - 定时数据：排名信息（从预计算表读取，缓存24小时）
    """
    dashboard_data = await home_service.get_dashboard_data(db=db, user_id=request.user.id)
    return response_base.success(data=dashboard_data)


@router.post('/check-in', summary='用户打卡', name='home_check_in')
async def check_in(
    db: CurrentSessionTransaction,
    obj: CheckInParam,
    request: Request, _token: str = DependsJwtAuth,
) -> ResponseSchemaModel:
    """
    👤 客户端首页 - 用户打卡

    在用户完成一定数量的做题后触发打卡

    参数说明：
    - practice_count: 当日做题数
    - practice_duration: 当日练习时长（秒）

    注意：
    - 同一天多次打卡会更新数据（不会重复创建）
    - 打卡记录用于计算连续打卡天数
    """
    await check_in_service.check_in(
        db=db,
        user_id=request.user.id,
        practice_count=obj.practice_count,
        practice_duration=obj.practice_duration,
    )
    return response_base.success()


@router.get('/check-in-calendar', summary='获取打卡日历', name='home_check_in_calendar')
async def get_check_in_calendar(
    db: CurrentSession,
    request: Request, _token: str = DependsJwtAuth,
    year: int = Query(default=None, description='年份（默认当前年）'),
    month: int = Query(default=None, description='月份（默认当前月，1-12）'),
) -> ResponseSchemaModel[CheckInCalendarData]:
    """
    👤 客户端首页 - 获取打卡日历

    获取指定月份的打卡日历数据，包括每天的打卡状态和做题数

    返回数据：
    - year: 年份
    - month: 月份
    - days: 每天的打卡数据列表
    - total_check_in_days: 本月打卡天数
    """
    today = date.today()
    year = year or today.year
    month = month or today.month

    calendar_data = await check_in_service.get_check_in_calendar(
        db=db,
        user_id=request.user.id,
        year=year,
        month=month,
    )
    return response_base.success(data=calendar_data)


@router.get('/rank', summary='获取排行榜列表', name='home_rank_list')
async def get_rank_list(
    db: CurrentSession,
    request: Request, _token: str = DependsJwtAuth,
    rank_type: str = Query(
        default='practice_count',
        description='排行榜类型（practice_count: 刷题数量, accuracy_rate: 正确率, streak_days: 坚持天数）',
    ),
    limit: int = Query(default=100, ge=1, le=500, description='返回数量（默认 100，最大 500）'),
) -> ResponseSchemaModel[RankListData]:
    """
    👤 客户端首页 - 获取排行榜列表

    获取排行榜数据，支持三种排行榜类型：
    - practice_count: 刷题数量排行榜
    - accuracy_rate: 正确率排行榜（要求至少做过 10 题）
    - streak_days: 坚持天数排行榜（连续打卡天数）

    返回数据：
    - rank_type: 排行榜类型
    - current_user_rank: 当前用户排名（如果在前 N 名中）
    - top_users: 排行榜用户列表

    性能优化：
    - 刷题数量：SQL 聚合查询，性能高
    - 正确率：SQL 聚合 + Python 排序（需要至少 10 题）
    - 坚持天数：遍历所有用户计算连续打卡（适合小规模用户）
    """
    rank_data = await rank_service.get_rank_list(
        db=db,
        rank_type=rank_type,
        current_user_id=request.user.id,
        limit=limit,
    )
    return response_base.success(data=rank_data)



