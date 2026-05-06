#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pydantic import BaseModel


class VisitStatsResponse(BaseModel):
    """访问统计响应"""
    recent_active: int = 0       # 最近活跃访客
    today_uv: int = 0            # 今日访问人数
    today_pv: int = 0            # 今日访问量
    yesterday_uv: int = 0        # 昨日访问人数
    yesterday_pv: int = 0        # 昨日访问量
    month_pv: int = 0            # 本月访问量
    total_pv: int = 0            # 总访问量
