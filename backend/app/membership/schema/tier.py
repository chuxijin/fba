#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class CreateMembershipTierParam(SchemaBase):
    """创建会员等级"""

    family_code: str = Field(min_length=1, max_length=16, description='等级族群(FREE/VIP/SVIP)')
    code: str = Field(min_length=1, max_length=32, description='等级编码')
    name: str = Field(min_length=1, max_length=64, description='等级名称')
    grade: int = Field(ge=0, le=10, description='族群内等级')
    exp_required: int = Field(default=0, ge=0, description='达到该等级所需经验')
    weight: int = Field(ge=0, le=32767, description='等级权重')
    sort: int = Field(default=0, description='排序')
    is_default: bool = Field(default=False, description='是否默认等级')
    status: int = Field(default=1, ge=0, le=1, description='状态(0停用 1启用)')
    description: str | None = Field(default=None, description='描述')


class UpdateMembershipTierParam(SchemaBase):
    """更新会员等级"""

    family_code: str | None = Field(default=None, min_length=1, max_length=16, description='等级族群(FREE/VIP/SVIP)')
    code: str | None = Field(default=None, min_length=1, max_length=32, description='等级编码')
    name: str | None = Field(default=None, min_length=1, max_length=64, description='等级名称')
    grade: int | None = Field(default=None, ge=0, le=10, description='族群内等级')
    exp_required: int | None = Field(default=None, ge=0, description='达到该等级所需经验')
    weight: int | None = Field(default=None, ge=0, le=32767, description='等级权重')
    sort: int | None = Field(default=None, description='排序')
    is_default: bool | None = Field(default=None, description='是否默认等级')
    status: int | None = Field(default=None, ge=0, le=1, description='状态(0停用 1启用)')
    description: str | None = Field(default=None, description='描述')


class GetMembershipTierDetail(SchemaBase):
    """会员等级详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='等级 ID')
    family_code: str = Field(description='等级族群')
    code: str = Field(description='等级编码')
    name: str = Field(description='等级名称')
    grade: int = Field(description='族群内等级')
    exp_required: int = Field(description='达到该等级所需经验')
    weight: int = Field(description='等级权重')
    sort: int = Field(description='排序')
    is_default: bool = Field(description='是否默认等级')
    status: int = Field(description='状态')
    description: str | None = Field(default=None, description='描述')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(default=None, description='更新时间')


class GetMembershipTierBrief(SchemaBase):
    """会员等级简要"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='等级 ID')
    family_code: str = Field(description='等级族群')
    code: str = Field(description='等级编码')
    name: str = Field(description='等级名称')
    grade: int = Field(description='族群内等级')
    weight: int = Field(description='等级权重')
    is_default: bool = Field(description='是否默认等级')
