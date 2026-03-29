#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class CreateMembershipEntitlementParam(SchemaBase):
    """创建会员权益"""

    code: str = Field(min_length=1, max_length=64, description='权益编码')
    name: str = Field(min_length=1, max_length=64, description='权益名称')
    value_type: str = Field(default='bool', description='权益值类型(bool/int)')
    default_value: int = Field(default=0, description='默认值')
    sort: int = Field(default=0, description='排序')
    status: int = Field(default=1, ge=0, le=1, description='状态(0停用 1启用)')
    description: str | None = Field(default=None, description='描述')


class UpdateMembershipEntitlementParam(SchemaBase):
    """更新会员权益"""

    code: str | None = Field(default=None, min_length=1, max_length=64, description='权益编码')
    name: str | None = Field(default=None, min_length=1, max_length=64, description='权益名称')
    value_type: str | None = Field(default=None, description='权益值类型(bool/int)')
    default_value: int | None = Field(default=None, description='默认值')
    sort: int | None = Field(default=None, description='排序')
    status: int | None = Field(default=None, ge=0, le=1, description='状态(0停用 1启用)')
    description: str | None = Field(default=None, description='描述')


class SetTierEntitlementItem(SchemaBase):
    """设置等级权益项"""

    entitlement_code: str = Field(min_length=1, max_length=64, description='权益编码')
    value: int = Field(default=1, description='权益值')
    status: int = Field(default=1, ge=0, le=1, description='状态(0停用 1启用)')
    description: str | None = Field(default=None, description='描述')


class SetTierEntitlementsParam(SchemaBase):
    """批量设置等级权益"""

    items: list[SetTierEntitlementItem] = Field(default_factory=list, description='权益项列表')


class GetMembershipEntitlementDetail(SchemaBase):
    """会员权益详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='权益 ID')
    code: str = Field(description='权益编码')
    name: str = Field(description='权益名称')
    value_type: str = Field(description='权益值类型')
    default_value: int = Field(description='默认值')
    sort: int = Field(description='排序')
    status: int = Field(description='状态')
    description: str | None = Field(default=None, description='描述')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(default=None, description='更新时间')


class GetTierEntitlementBrief(SchemaBase):
    """等级权益简要"""

    model_config = ConfigDict(from_attributes=True)

    entitlement_code: str = Field(description='权益编码')
    value: int = Field(description='权益值')
    status: int = Field(description='状态')
    description: str | None = Field(default=None, description='描述')
