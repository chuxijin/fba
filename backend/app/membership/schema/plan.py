#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class CreateMembershipPlanParam(SchemaBase):
    """创建会员计划"""

    name: str = Field(description='计划名称')
    level: int = Field(default=0, ge=0, le=3, description='等级层次(0免费 1基础 2高级 3至尊)')
    role_id: int = Field(description='关联角色 ID')
    duration_days: int = Field(gt=0, description='默认时长天数')
    price: int = Field(default=0, ge=0, description='价格(分)')
    original_price: int = Field(default=0, ge=0, description='原价(分)')
    description: str | None = Field(default=None, description='权益描述')
    sort: int = Field(default=0, description='排序')
    status: int = Field(default=1, ge=0, le=1, description='状态(0下架 1上架)')


class UpdateMembershipPlanParam(SchemaBase):
    """更新会员计划"""

    name: str | None = Field(default=None, description='计划名称')
    level: int | None = Field(default=None, ge=0, le=3, description='等级层次(0免费 1基础 2高级 3至尊)')
    role_id: int | None = Field(default=None, description='关联角色 ID')
    duration_days: int | None = Field(default=None, gt=0, description='默认时长天数')
    price: int | None = Field(default=None, ge=0, description='价格(分)')
    original_price: int | None = Field(default=None, ge=0, description='原价(分)')
    description: str | None = Field(default=None, description='权益描述')
    sort: int | None = Field(default=None, description='排序')
    status: int | None = Field(default=None, ge=0, le=1, description='状态(0下架 1上架)')


class GetMembershipPlanDetail(SchemaBase):
    """会员计划详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='计划 ID')
    name: str = Field(description='计划名称')
    level: int = Field(description='等级层次')
    role_id: int = Field(description='关联角色 ID')
    duration_days: int = Field(description='默认时长天数')
    price: int = Field(description='价格(分)')
    original_price: int = Field(description='原价(分)')
    description: str | None = Field(default=None, description='权益描述')
    sort: int = Field(description='排序')
    status: int = Field(description='状态')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(default=None, description='更新时间')


class GetMembershipPlanBrief(SchemaBase):
    """会员计划简要"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='计划 ID')
    name: str = Field(description='计划名称')
    level: int = Field(description='等级层次')
    duration_days: int = Field(description='默认时长天数')
    price: int = Field(description='价格(分)')
    original_price: int = Field(description='原价(分)')
    description: str | None = Field(default=None, description='权益描述')
