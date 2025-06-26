#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pydantic import BaseModel, Field


class AppAuthStatistics(BaseModel):
    """应用授权统计数据"""
    applications: int = Field(..., description='应用总数')
    devices: int = Field(..., description='设备总数')
    authorizations: int = Field(..., description='有效授权数')
    redeem_codes: int = Field(..., description='兑换码总数')
    active_authorizations: int = Field(..., description='活跃授权数')
    expired_authorizations: int = Field(..., description='过期授权数')
    total_orders: int = Field(..., description='订单总数')
    total_packages: int = Field(..., description='套餐总数') 