#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from pydantic import AliasChoices, ConfigDict, Field

from backend.app.access.constants import CommonStatus
from backend.common.schema import SchemaBase


class CreateMembershipTierParam(SchemaBase):
    """创建会员档位"""

    code: str = Field(max_length=32, description='档位编码')
    name: str = Field(max_length=64, description='档位名称')
    weight: int = Field(default=0, ge=0, description='展示排序权重')
    is_paid: bool = Field(default=False, description='是否属于付费会员')
    badge_color: str | None = Field(default=None, max_length=16, description='徽章主题色')
    description: str | None = Field(default=None, description='描述')
    display_order: int = Field(default=0, description='显示顺序')
    status: CommonStatus = Field(default=CommonStatus.ACTIVE, description='状态')
    metadata_: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices('metadata', 'metadata_'),
        serialization_alias='metadata',
        description='扩展展示配置',
    )


class UpdateMembershipTierParam(SchemaBase):
    """更新会员档位"""

    name: str | None = Field(default=None, max_length=64, description='档位名称')
    weight: int | None = Field(default=None, ge=0, description='展示排序权重')
    is_paid: bool | None = Field(default=None, description='是否属于付费会员')
    badge_color: str | None = Field(default=None, max_length=16, description='徽章主题色')
    description: str | None = Field(default=None, description='描述')
    display_order: int | None = Field(default=None, description='显示顺序')
    metadata_: dict[str, Any] | None = Field(
        default=None,
        validation_alias=AliasChoices('metadata', 'metadata_'),
        serialization_alias='metadata',
        description='扩展展示配置',
    )
    status: CommonStatus | None = Field(default=None, description='状态')


class GetMembershipTierDetail(SchemaBase):
    """会员档位详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='档位 ID')
    code: str = Field(description='档位编码')
    name: str = Field(description='档位名称')
    weight: int = Field(description='展示排序权重')
    is_paid: bool = Field(description='是否属于付费会员')
    badge_color: str | None = Field(description='徽章主题色')
    description: str | None = Field(description='描述')
    display_order: int = Field(description='显示顺序')
    metadata_: dict[str, Any] = Field(
        default_factory=dict,
        validation_alias=AliasChoices('metadata_', 'metadata'),
        serialization_alias='metadata',
        description='扩展展示配置',
    )
    status: CommonStatus = Field(description='状态')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(default=None, description='更新时间')
