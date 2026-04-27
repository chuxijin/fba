#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class OpenMembershipParam(SchemaBase):
    """开通会员"""

    user_id: int = Field(description='用户 ID')
    plan_id: int = Field(description='会员计划 ID')
    source: str = Field(default='admin', description='来源')
    source_key: str = Field(min_length=1, max_length=64, description='来源幂等键')
    remark: str | None = Field(default=None, description='备注')


class AddDaysParam(SchemaBase):
    """增加会员天数"""

    user_id: int = Field(description='用户 ID')
    plan_id: int = Field(description='会员计划 ID')
    days: int = Field(gt=0, description='增加天数')
    source: str = Field(default='admin', description='来源标识')
    source_key: str = Field(min_length=1, max_length=64, description='来源幂等键')
    source_detail: str | None = Field(default=None, description='来源详情')
    remark: str | None = Field(default=None, description='备注')


class GetUserMembershipDetail(SchemaBase):
    """用户会员详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='记录 ID')
    user_id: int = Field(description='用户 ID')
    family_code: str = Field(description='等级族群')
    tier_id: int = Field(description='会员等级 ID')
    tier_code: str = Field(description='等级编码')
    tier_name: str = Field(description='等级名称')
    tier_grade: int = Field(description='族群内等级')
    tier_weight: int = Field(description='等级权重')
    exp: int = Field(description='经验值')
    available_exp: int = Field(description='可用经验值')
    valid_from: datetime | None = Field(default=None, description='有效期开始')
    valid_to: datetime | None = Field(default=None, description='有效期结束')
    source: str = Field(description='来源')
    source_key: str | None = Field(default=None, description='来源幂等键')
    status: int = Field(description='状态')
    remark: str | None = Field(default=None, description='备注')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(default=None, description='更新时间')


class GetUserMembershipBrief(SchemaBase):
    """用户会员简要"""

    model_config = ConfigDict(from_attributes=True)

    family_code: str = Field(description='等级族群')
    tier_id: int = Field(description='会员等级 ID')
    tier_code: str = Field(description='等级编码')
    tier_name: str = Field(description='等级名称')
    tier_grade: int = Field(description='族群内等级')
    tier_weight: int = Field(description='等级权重')
    exp: int = Field(description='经验值')
    available_exp: int = Field(description='可用经验值')
    valid_from: datetime | None = Field(default=None, description='有效期开始')
    valid_to: datetime | None = Field(default=None, description='有效期结束')
    status: int = Field(description='状态')


class AddExperienceParam(SchemaBase):
    """增加经验值"""

    user_id: int = Field(description='用户 ID')
    family_code: str = Field(min_length=1, max_length=16, description='等级族群(FREE/VIP/SVIP)')
    exp_delta: int = Field(gt=0, description='经验增量')
    source: str = Field(default='activity', description='来源标识')
    source_key: str = Field(min_length=1, max_length=64, description='来源幂等键')
    remark: str | None = Field(default=None, description='备注')


class ConsumeExperienceParam(SchemaBase):
    """消耗经验值"""

    user_id: int = Field(description='用户 ID')
    family_code: str = Field(min_length=1, max_length=16, description='等级族群(FREE/VIP/SVIP)')
    exp_delta: int = Field(gt=0, description='消耗经验值')
    source: str = Field(default='exchange', description='来源标识')
    source_key: str = Field(min_length=1, max_length=64, description='来源幂等键')
    remark: str | None = Field(default=None, description='备注')
