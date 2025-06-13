#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import Field

from backend.common.schema import SchemaBase


class CreateApplicationParam(SchemaBase):
    """创建应用参数"""

    name: str = Field(description='应用名称')
    app_key: str = Field(description='应用标识')
    description: str | None = Field(None, description='应用描述')
    icon: str | None = Field(None, description='应用图标')
    is_free: bool = Field(False, description='是否免费')


class UpdateApplicationParam(SchemaBase):
    """更新应用参数"""

    name: str | None = Field(None, description='应用名称')
    description: str | None = Field(None, description='应用描述')
    icon: str | None = Field(None, description='应用图标')
    status: int | None = Field(None, description='状态')
    is_free: bool | None = Field(None, description='是否免费')


class GetApplicationDetail(SchemaBase):
    """应用详情"""

    id: int = Field(description='应用ID')
    name: str = Field(description='应用名称')
    app_key: str = Field(description='应用标识')
    description: str | None = Field(description='应用描述')
    icon: str | None = Field(description='应用图标')
    status: int = Field(description='状态')
    is_free: bool = Field(description='是否免费')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(description='更新时间')