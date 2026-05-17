#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field

from backend.app.access.constants import CommonStatus, TemplateKind
from backend.app.access.schema.base import TimePeriodInput, TimePeriodOutput
from backend.app.access.schema.pack import GetPackDetail
from backend.common.schema import SchemaBase


class CreateTemplateParam(SchemaBase):
    """创建订阅模板"""

    code: str = Field(max_length=64, description='模板编码')
    name: str = Field(max_length=128, description='模板名称')
    kind: TemplateKind = Field(default=TemplateKind.STANDARD, description='模板类型')
    duration_days: int | None = Field(default=None, description='时长天数, 空表示永久')
    auto_renewable: bool = Field(default=False, description='是否自动续费')
    price_cents: int = Field(default=0, description='价格(分)')
    display_order: int = Field(default=0, description='显示顺序')
    cover_image: str | None = Field(default=None, max_length=512, description='封面图')
    description: str | None = Field(default=None, description='描述')
    sale_period: TimePeriodInput | None = Field(default=None, description='上架时间段')
    metadata: dict[str, Any] = Field(default_factory=dict, description='扩展元数据')
    pack_codes: list[str] = Field(default_factory=list, description='关联的权益包编码列表')


class UpdateTemplateParam(SchemaBase):
    """更新订阅模板"""

    name: str | None = Field(default=None, max_length=128, description='模板名称')
    kind: TemplateKind | None = Field(default=None, description='模板类型')
    duration_days: int | None = Field(default=None, description='时长天数')
    auto_renewable: bool | None = Field(default=None, description='是否自动续费')
    price_cents: int | None = Field(default=None, description='价格(分)')
    display_order: int | None = Field(default=None, description='显示顺序')
    cover_image: str | None = Field(default=None, max_length=512, description='封面图')
    description: str | None = Field(default=None, description='描述')
    sale_period: TimePeriodInput | None = Field(default=None, description='上架时间段')
    metadata: dict[str, Any] | None = Field(default=None, description='扩展元数据')
    status: CommonStatus | None = Field(default=None, description='状态')


class SetTemplatePacksParam(SchemaBase):
    """批量设置模板关联的权益包"""

    pack_codes: list[str] = Field(description='权益包编码列表')


class GetTemplateDetail(SchemaBase):
    """订阅模板详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='模板 ID')
    code: str = Field(description='模板编码')
    name: str = Field(description='模板名称')
    kind: TemplateKind = Field(description='模板类型')
    duration_days: int | None = Field(description='时长天数')
    auto_renewable: bool = Field(description='是否自动续费')
    price_cents: int = Field(description='价格(分)')
    display_order: int = Field(description='显示顺序')
    cover_image: str | None = Field(description='封面图')
    description: str | None = Field(description='描述')
    sale_period: TimePeriodOutput | None = Field(default=None, description='上架时间段')
    status: CommonStatus = Field(description='状态')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(default=None, description='更新时间')


class GetTemplateDetailWithPacks(GetTemplateDetail):
    """订阅模板详情(含关联权益包)"""

    packs: list[GetPackDetail] = Field(default_factory=list, description='关联的权益包')
