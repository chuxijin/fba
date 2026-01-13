#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class LogSchemaBase(SchemaBase):
    """访问日志基础模型"""

    type: int = Field(ge=1, le=3, description='类型(1短链 2群活码 3客服码)')
    target_id: int = Field(description='目标ID')
    ip: str | None = Field(None, max_length=64, description='访问IP')
    device: str | None = Field(None, max_length=32, description='设备')
    reference: str | None = Field(None, max_length=64, description='来源')
    user_agent: str | None = Field(None, max_length=512, description='浏览器UA')
    country: str | None = Field(None, max_length=64, description='国家')
    city: str | None = Field(None, max_length=64, description='城市')


class CreateLogParam(LogSchemaBase):
    """创建访问日志参数"""

    pv: int = Field(1, ge=1, description='访问次数')


class GetLogDetail(LogSchemaBase):
    """访问日志详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='日志ID')
    pv: int = Field(description='访问次数')
    created_time: datetime = Field(description='访问时间')


class LogStatistics(SchemaBase):
    """访问统计"""

    total_clicks: int = Field(description='总访问量')
    today_clicks: int = Field(description='今日访问量')
    device_stats: dict[str, int] = Field(description='设备统计')
    reference_stats: dict[str, int] = Field(description='来源统计')
