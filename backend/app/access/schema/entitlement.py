#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.app.access.constants import (
    CommonStatus,
    EntitlementCategory,
    EntitlementMetric,
    EntitlementVerb,
)
from backend.common.schema import SchemaBase


class CreateEntitlementParam(SchemaBase):
    """创建权益"""

    code: str = Field(max_length=64, description='权益编码')
    name: str = Field(max_length=128, description='权益名')
    category: EntitlementCategory = Field(description='权益分类')
    metric: EntitlementMetric = Field(default=EntitlementMetric.BOOLEAN, description='度量类型')
    verb: EntitlementVerb = Field(default=EntitlementVerb.ACCESS, description='动作')
    domain_id: int | None = Field(default=None, description='所属领域 ID')
    resource_type: str | None = Field(default=None, max_length=32, description='资源类型')
    description: str | None = Field(default=None, description='描述')


class UpdateEntitlementParam(SchemaBase):
    """更新权益"""

    name: str | None = Field(default=None, max_length=128, description='权益名')
    metric: EntitlementMetric | None = Field(default=None, description='度量类型')
    verb: EntitlementVerb | None = Field(default=None, description='动作')
    domain_id: int | None = Field(default=None, description='所属领域 ID')
    resource_type: str | None = Field(default=None, max_length=32, description='资源类型')
    description: str | None = Field(default=None, description='描述')
    status: CommonStatus | None = Field(default=None, description='状态')


class EntitlementQueryParam(SchemaBase):
    """权益查询"""

    keyword: str | None = Field(default=None, description='关键字')
    category: EntitlementCategory | None = Field(default=None, description='分类')
    verb: EntitlementVerb | None = Field(default=None, description='动作')
    domain_id: int | None = Field(default=None, description='领域 ID')
    resource_type: str | None = Field(default=None, description='资源类型')
    status: CommonStatus | None = Field(default=None, description='状态')


class GetEntitlementDetail(SchemaBase):
    """权益详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='权益 ID')
    code: str = Field(description='权益编码')
    name: str = Field(description='权益名')
    category: EntitlementCategory = Field(description='权益分类')
    metric: EntitlementMetric = Field(description='度量类型')
    verb: EntitlementVerb = Field(description='动作')
    domain_id: int | None = Field(description='所属领域 ID')
    resource_type: str | None = Field(description='资源类型')
    description: str | None = Field(description='描述')
    status: CommonStatus = Field(description='状态')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(default=None, description='更新时间')
