#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from pydantic import AliasChoices, ConfigDict, Field

from backend.app.access.constants import CommonStatus
from backend.common.schema import SchemaBase


class CreateStudyDomainParam(SchemaBase):
    """创建学习领域"""

    code: str = Field(max_length=32, description='领域编码')
    name: str = Field(max_length=64, description='显示名')
    short_name: str | None = Field(default=None, max_length=32, description='营销短名')
    parent_id: int | None = Field(default=None, description='父级领域 ID')
    icon: str | None = Field(default=None, max_length=512, description='图标')
    color: str | None = Field(default=None, max_length=16, description='主题色')
    description: str | None = Field(default=None, description='描述')
    display_order: int = Field(default=0, description='显示顺序')
    metadata_: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices('metadata', 'metadata_'),
        serialization_alias='metadata',
        description='扩展元数据',
    )


class UpdateStudyDomainParam(SchemaBase):
    """更新学习领域"""

    name: str | None = Field(default=None, max_length=64, description='显示名')
    short_name: str | None = Field(default=None, max_length=32, description='营销短名')
    parent_id: int | None = Field(default=None, description='父级领域 ID')
    icon: str | None = Field(default=None, max_length=512, description='图标')
    color: str | None = Field(default=None, max_length=16, description='主题色')
    description: str | None = Field(default=None, description='描述')
    display_order: int | None = Field(default=None, description='显示顺序')
    metadata_: dict[str, Any] | None = Field(
        default=None,
        validation_alias=AliasChoices('metadata', 'metadata_'),
        serialization_alias='metadata',
        description='扩展元数据',
    )
    status: CommonStatus | None = Field(default=None, description='状态')


class GetStudyDomainDetail(SchemaBase):
    """领域详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='领域 ID')
    code: str = Field(description='领域编码')
    name: str = Field(description='显示名')
    short_name: str | None = Field(description='营销短名')
    parent_id: int | None = Field(description='父级领域 ID')
    icon: str | None = Field(description='图标')
    color: str | None = Field(description='主题色')
    description: str | None = Field(description='描述')
    display_order: int = Field(description='显示顺序')
    metadata_: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices('metadata_', 'metadata'),
        serialization_alias='metadata',
        description='扩展元数据',
    )
    status: CommonStatus = Field(description='状态')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(default=None, description='更新时间')
