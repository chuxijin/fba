#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field

from backend.app.access.constants import CommonStatus, GrantSource
from backend.app.access.schema.base import TimePeriodInput, TimePeriodOutput
from backend.common.schema import SchemaBase


class CreateDirectGrantParam(SchemaBase):
    """创建直接授予"""

    user_id: int = Field(description='用户 ID')
    entitlement_code: str = Field(max_length=64, description='权益编码')
    valid_period: TimePeriodInput = Field(description='有效时间段')
    source: GrantSource = Field(description='授予来源')
    value_int: int | None = Field(default=None, description='附带数值')
    value_meta: dict[str, Any] = Field(default_factory=dict, description='扩展参数')
    source_ref: str | None = Field(default=None, max_length=128, description='来源引用')
    reason: str | None = Field(default=None, max_length=256, description='授予原因')


class GetDirectGrantDetail(SchemaBase):
    """直接授予详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='授予 ID')
    user_id: int = Field(description='用户 ID')
    entitlement_code: str = Field(description='权益编码')
    valid_period: TimePeriodOutput = Field(description='有效时间段')
    source: GrantSource = Field(description='授予来源')
    value_int: int | None = Field(description='附带数值')
    value_meta: dict[str, Any] = Field(description='扩展参数')
    source_ref: str | None = Field(description='来源引用')
    reason: str | None = Field(description='授予原因')
    status: CommonStatus = Field(description='状态')
    created_time: datetime = Field(description='创建时间')
