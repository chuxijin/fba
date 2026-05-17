#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field

from backend.app.access.constants import CommonStatus, GradeLevel
from backend.common.schema import SchemaBase


class CreatePackParam(SchemaBase):
    """创建权益包"""

    code: str = Field(max_length=64, description='包编码')
    name: str = Field(max_length=128, description='包名称')
    grade: GradeLevel = Field(default=GradeLevel.STANDARD, description='档次')
    domain_id: int | None = Field(default=None, description='所属领域 ID')
    description: str | None = Field(default=None, description='描述')


class UpdatePackParam(SchemaBase):
    """更新权益包"""

    name: str | None = Field(default=None, max_length=128, description='包名称')
    grade: GradeLevel | None = Field(default=None, description='档次')
    domain_id: int | None = Field(default=None, description='所属领域 ID')
    description: str | None = Field(default=None, description='描述')
    status: CommonStatus | None = Field(default=None, description='状态')


class PackItemInput(SchemaBase):
    """权益包成员入参"""

    entitlement_code: str = Field(description='权益编码')
    value_int: int | None = Field(default=None, description='整数值(配额上限)')
    value_meta: dict[str, Any] = Field(default_factory=dict, description='扩展参数')


class SetPackItemsParam(SchemaBase):
    """批量设置权益包成员"""

    items: list[PackItemInput] = Field(default_factory=list, description='成员列表')


class GetPackItemDetail(SchemaBase):
    """权益包成员详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='成员 ID')
    pack_id: int = Field(description='包 ID')
    entitlement_id: int = Field(description='权益 ID')
    entitlement_code: str = Field(description='权益编码')
    entitlement_name: str = Field(description='权益名')
    value_int: int | None = Field(description='整数值')
    value_meta: dict[str, Any] = Field(description='扩展参数')
    status: CommonStatus = Field(description='状态')


class GetPackDetail(SchemaBase):
    """权益包详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='包 ID')
    code: str = Field(description='包编码')
    name: str = Field(description='包名称')
    grade: GradeLevel = Field(description='档次')
    domain_id: int | None = Field(description='所属领域 ID')
    description: str | None = Field(description='描述')
    status: CommonStatus = Field(description='状态')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(default=None, description='更新时间')


class GetPackDetailWithItems(GetPackDetail):
    """权益包详情(含成员)"""

    items: list[GetPackItemDetail] = Field(default_factory=list, description='成员列表')
