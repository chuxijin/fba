#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from pydantic import Field, field_validator

from backend.common.schema import SchemaBase


class CloudEvent(SchemaBase):
    """CloudEvents v1.0 标准信封"""

    specversion: str = Field('1.0', description='规范版本')
    id: str = Field(description='事件唯一 ID')
    type: str = Field(description='事件类型')
    source: str = Field(description='事件来源 URI')
    time: datetime | None = Field(None, description='事件发生时间 (RFC3339)')
    datacontenttype: str = Field('application/json', description='数据 MIME 类型')
    subject: str | None = Field(None, description='关联资源标识')
    dataschema: str | None = Field(None, description='数据 Schema URI')
    data: dict[str, Any] | None = Field(None, description='事件数据')

    @field_validator('specversion')
    @classmethod
    def validate_specversion(cls, v: str) -> str:
        """验证规范版本"""
        if v != '1.0':
            raise ValueError('仅支持 CloudEvents v1.0')
        return v

    @field_validator('type')
    @classmethod
    def validate_type(cls, v: str) -> str:
        """验证事件类型格式"""
        if not v or '.' not in v:
            raise ValueError('事件类型必须使用点分格式, 如 com.fba.order.created')
        return v


class CloudEventCreate(SchemaBase):
    """创建 CloudEvents 事件参数 (简化版, 用于手动发布)"""

    type: str = Field(description='事件类型')
    source: str = Field('/services/fba', description='事件来源')
    data: dict[str, Any] | None = Field(None, description='事件数据')
    subject: str | None = Field(None, description='关联资源标识')
