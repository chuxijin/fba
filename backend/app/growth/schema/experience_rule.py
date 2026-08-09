#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class CreateExperienceRuleParam(SchemaBase):
    """创建经验规则"""

    event_code: str = Field(max_length=32, description='事件编码')
    name: str = Field(max_length=64, description='规则名称')
    exp_delta: int = Field(gt=0, description='经验奖励值')
    required_entitlement_code: str | None = Field(
        default=None,
        max_length=64,
        description='生效所需权益编码, 空表示对所有用户生效',
    )
    cycle_day: int | None = Field(default=None, description='周期第几天')
    min_practice_count: int = Field(default=0, ge=0, description='最低做题数')
    min_practice_duration: int = Field(default=0, ge=0, description='最低练习时长(秒)')
    sort: int = Field(default=0, description='排序')
    description: str | None = Field(default=None, description='描述')


class UpdateExperienceRuleParam(SchemaBase):
    """更新经验规则"""

    name: str | None = Field(default=None, max_length=64, description='规则名称')
    exp_delta: int | None = Field(default=None, gt=0, description='经验奖励值')
    required_entitlement_code: str | None = Field(
        default=None,
        max_length=64,
        description='生效所需权益编码, 空表示对所有用户生效',
    )
    cycle_day: int | None = Field(default=None, description='周期第几天')
    min_practice_count: int | None = Field(default=None, ge=0, description='最低做题数')
    min_practice_duration: int | None = Field(default=None, ge=0, description='最低练习时长(秒)')
    sort: int | None = Field(default=None, description='排序')
    status: int | None = Field(default=None, description='状态')
    description: str | None = Field(default=None, description='描述')


class GetExperienceRuleDetail(SchemaBase):
    """经验规则详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='规则 ID')
    event_code: str = Field(description='事件编码')
    name: str = Field(description='规则名称')
    exp_delta: int = Field(description='经验奖励值')
    required_entitlement_code: str | None = Field(description='生效所需权益编码')
    cycle_day: int | None = Field(description='周期第几天')
    min_practice_count: int = Field(description='最低做题数')
    min_practice_duration: int = Field(description='最低练习时长(秒)')
    sort: int = Field(description='排序')
    status: int = Field(description='状态')
    description: str | None = Field(description='描述')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(default=None, description='更新时间')
