#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import timedelta
from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select

from backend.app.admin.model.user import User
from backend.app.admin.schema.dashboard import DashboardTrendItem, GetUserStatsResponse
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.exception import errors
from backend.database.db import CurrentSession
from backend.utils.timezone import timezone

router = APIRouter()


def admin_verify(request: Request, _token: str = DependsJwtAuth) -> bool:
    """
    验证管理员权限

    :param request: 请求对象
    :param _token: 令牌权限依赖
    :return:
    """
    from starlette.authentication import UnauthenticatedUser
    if isinstance(request.user, UnauthenticatedUser):
        raise errors.TokenError

    if not (request.user.is_superuser or request.user.is_staff):
        raise errors.AuthorizationError(msg='权限不足，仅管理员可访问')
    return True


DependsAdminUser = Depends(admin_verify)


@router.get('/user-stats', summary='获取管理面板用户统计', dependencies=[DependsAdminUser])
async def get_dashboard_user_stats(db: CurrentSession) -> ResponseSchemaModel[GetUserStatsResponse]:
    """
    获取用户新增统计概览及周期趋势

    :param db: 数据库会话
    :return:
    """
    # 1. 统计总用户数
    stmt_total = select(func.count(User.id))
    total_users = (await db.execute(stmt_total)).scalar_one()

    # 2. 统计今日新增用户数
    now = timezone.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    stmt_today = select(func.count(User.id)).where(User.join_time >= today_start)
    today_new_users = (await db.execute(stmt_today)).scalar_one()

    # 3. 统计近 30 天趋势数据
    thirty_days_ago = today_start - timedelta(days=30)
    stmt_records = select(User.join_time).where(User.join_time >= thirty_days_ago)
    records = (await db.execute(stmt_records)).scalars().all()

    # 初始化近 30 天每日统计
    dates_30 = []
    daily_counts = {}
    for i in range(30):
        day_date = today_start - timedelta(days=29 - i)
        d_str = day_date.strftime('%m-%d')
        dates_30.append(d_str)
        daily_counts[d_str] = 0

    # 累加统计
    for record in records:
        local_t = timezone.from_datetime(record)
        d_str = local_t.strftime('%m-%d')
        if d_str in daily_counts:
            daily_counts[d_str] += 1

    # 组装 30 天趋势
    trend_30 = [
        DashboardTrendItem(date=d, count=daily_counts[d])
        for d in dates_30
    ]

    # 组装 7 天趋势
    trend_7 = trend_30[-7:]

    data = GetUserStatsResponse(
        total_users=total_users,
        today_new_users=today_new_users,
        trend_7_days=trend_7,
        trend_30_days=trend_30,
    )
    return response_base.success(data=data)
