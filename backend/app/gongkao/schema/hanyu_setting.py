#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class UpdateHanyuSettingParam(SchemaBase):
    """更新汉语学习设置参数"""

    daily_new_target: int | None = Field(None, ge=1, le=200, description='每日新词目标')
    daily_review_limit: int | None = Field(None, ge=0, le=1000, description='每日复习上限(0 不限)')
    auto_pronunciation: bool | None = Field(None, description='自动播放发音')


class GetHanyuSettingDetail(SchemaBase):
    """汉语学习设置详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='ID')
    user_id: int = Field(description='用户 ID')
    daily_new_target: int = Field(20, description='每日新词目标')
    daily_review_limit: int = Field(200, description='每日复习上限(0 不限)')
    auto_pronunciation: bool = Field(False, description='自动播放发音')
