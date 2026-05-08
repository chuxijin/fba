#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class UpdateSettingParam(SchemaBase):
    """更新学习设置参数"""

    daily_new_target: int | None = Field(None, ge=1, le=200, description='每日新词目标')
    daily_review_limit: int | None = Field(None, ge=0, le=1000, description='每日复习上限(0 不限)')
    reminder_enabled: bool | None = Field(None, description='是否开启提醒')
    reminder_time: str | None = Field(None, max_length=5, description='提醒时间(如 08:30)')
    preferred_mode: str | None = Field(None, max_length=20, description='偏好学习模式')
    auto_pronunciation: bool | None = Field(None, description='自动播放发音')
    pronunciation_type: str | None = Field(None, max_length=5, description='发音偏好(us/uk)')


class GetSettingDetail(SchemaBase):
    """学习设置详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='设置 ID')
    user_id: int = Field(description='用户 ID')
    daily_new_target: int = Field(description='每日新词目标')
    daily_review_limit: int = Field(description='每日复习上限')
    reminder_enabled: bool = Field(description='是否开启提醒')
    reminder_time: str | None = Field(None, description='提醒时间')
    preferred_mode: str = Field(description='偏好学习模式')
    auto_pronunciation: bool = Field(description='自动播放发音')
    pronunciation_type: str = Field(description='发音偏好')
