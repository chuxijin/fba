#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class DwzLogSchemaBase(SchemaBase):
    """短网址访问日志基础模型"""

    dwz_id: int = Field(description='短网址ID')
    ip: str | None = Field(None, max_length=64, description='访问IP')
    platform: str | None = Field(None, max_length=32, description='访问平台')
    user_agent: str | None = Field(None, max_length=512, description='浏览器UA')
    referer: str | None = Field(None, max_length=1024, description='来源页面')
    country: str | None = Field(None, max_length=64, description='国家')
    city: str | None = Field(None, max_length=64, description='城市')


class CreateDwzLogParam(DwzLogSchemaBase):
    """创建访问日志参数"""

    pass


class GetDwzLogDetail(DwzLogSchemaBase):
    """访问日志详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='日志ID')
    created_time: datetime = Field(description='访问时间')


class DwzStatistics(SchemaBase):
    """短网址统计数据"""

    total_clicks: int = Field(description='总访问量')
    today_clicks: int = Field(description='今日访问量')
    platform_stats: dict[str, int] = Field(description='平台访问统计')
    recent_logs: list[GetDwzLogDetail] = Field(description='最近访问记录')
