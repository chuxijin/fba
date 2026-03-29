#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class GetMembershipRecordDetail(SchemaBase):
    """会员流水详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='记录 ID')
    user_id: int = Field(description='用户 ID')
    family_code: str = Field(description='等级族群')
    tier_id: int = Field(description='会员等级 ID')
    plan_id: int | None = Field(default=None, description='会员计划 ID')
    op_type: str = Field(description='操作类型')
    days: int = Field(description='变动天数')
    exp_delta: int = Field(description='经验变动值')
    source: str = Field(description='来源标识')
    source_key: str = Field(description='来源幂等键')
    source_detail: str | None = Field(default=None, description='来源详情')
    valid_to_before: datetime | None = Field(default=None, description='变动前到期时间')
    valid_to_after: datetime | None = Field(default=None, description='变动后到期时间')
    remark: str | None = Field(default=None, description='备注')
    created_time: datetime = Field(description='创建时间')


class GetMembershipRecordBrief(SchemaBase):
    """会员流水简要"""

    model_config = ConfigDict(from_attributes=True)

    family_code: str = Field(description='等级族群')
    tier_id: int = Field(description='会员等级 ID')
    plan_id: int | None = Field(default=None, description='会员计划 ID')
    op_type: str = Field(description='操作类型')
    days: int = Field(description='变动天数')
    exp_delta: int = Field(description='经验变动值')
    source: str = Field(description='来源标识')
    source_key: str = Field(description='来源幂等键')
    valid_to_after: datetime | None = Field(default=None, description='变动后到期时间')
    created_time: datetime = Field(description='创建时间')
