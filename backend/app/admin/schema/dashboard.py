#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pydantic import Field

from backend.common.schema import SchemaBase


class DashboardTrendItem(SchemaBase):
    """趋势项"""

    date: str = Field(description='日期')
    count: int = Field(description='新增用户数')


class GetUserStatsResponse(SchemaBase):
    """用户统计详情"""

    total_users: int = Field(description='总用户数')
    today_new_users: int = Field(description='今日新增用户数')
    trend_7_days: list[DashboardTrendItem] = Field(description='近 7 天趋势')
    trend_30_days: list[DashboardTrendItem] = Field(description='近 30 天趋势')
