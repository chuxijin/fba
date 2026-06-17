#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.app.growth.constants import GrowthEventOp
from backend.common.schema import SchemaBase


class GetGrowthAccountDetail(SchemaBase):
    """成长账户详情"""

    model_config = ConfigDict(from_attributes=True)

    user_id: int = Field(description='用户 ID')
    total_exp: int = Field(description='累计经验')
    available_exp: int = Field(description='可用经验')
    current_grade: int = Field(description='当前等级')


class GetGrowthProgress(SchemaBase):
    """成长进度"""

    total_exp: int = Field(description='累计经验')
    available_exp: int = Field(description='可用经验')
    current_grade: int = Field(description='当前等级')
    next_exp_required: int | None = Field(default=None, description='下一级所需经验')


class AddExperienceParam(SchemaBase):
    """加经验值"""

    user_id: int = Field(description='用户 ID')
    exp_delta: int = Field(gt=0, description='经验增量')
    source: str = Field(max_length=32, description='来源标识')
    source_key: str = Field(max_length=128, description='来源幂等键')
    reason: str | None = Field(default=None, max_length=256, description='原因')


class GetGrowthEventDetail(SchemaBase):
    """成长事件流水"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='事件 ID')
    user_id: int = Field(description='用户 ID')
    family_code: str = Field(description='族群')
    operation: GrowthEventOp = Field(description='操作类型')
    exp_delta: int = Field(description='变动量')
    total_exp_after: int = Field(description='操作后累计')
    available_exp_after: int = Field(description='操作后可用')
    grade_after: int = Field(description='操作后等级')
    source: str = Field(description='来源')
    source_key: str | None = Field(description='来源键')
    reason: str | None = Field(description='原因')
    occurred_at: datetime = Field(description='发生时间')
