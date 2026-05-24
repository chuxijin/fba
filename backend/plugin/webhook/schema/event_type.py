#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class CreateEventTypeParam(SchemaBase):
    """创建事件类型参数"""

    type_key: str = Field(min_length=1, max_length=200, description='事件类型标识')
    category: str = Field(min_length=1, max_length=50, description='分类')
    description: str | None = Field(None, max_length=500, description='描述')
    payload_schema: dict[str, Any] | None = Field(None, description='payload JSON Schema')
    is_active: bool = Field(True, description='是否启用')


class UpdateEventTypeParam(SchemaBase):
    """更新事件类型参数"""

    category: str | None = Field(None, max_length=50, description='分类')
    description: str | None = Field(None, max_length=500, description='描述')
    payload_schema: dict[str, Any] | None = Field(None, description='payload JSON Schema')
    is_active: bool | None = Field(None, description='是否启用')


class GetEventTypeDetail(SchemaBase):
    """事件类型详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='事件类型 ID')
    type_key: str = Field(description='事件类型标识')
    category: str = Field(description='分类')
    description: str | None = Field(None, description='描述')
    payload_schema: dict[str, Any] | None = Field(None, description='payload JSON Schema')
    is_active: bool = Field(description='是否启用')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class EventTypeListParam(SchemaBase):
    """事件类型列表查询参数"""

    category: str | None = Field(None, description='分类')
    is_active: bool | None = Field(None, description='是否启用')
