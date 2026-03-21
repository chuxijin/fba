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
    remark: str | None = Field(default=None, description='备注')


class AddDaysParam(SchemaBase):
    """增加会员天数"""

    user_id: int = Field(description='用户 ID')
    plan_id: int = Field(description='会员计划 ID')
    days: int = Field(gt=0, description='增加天数')
    source: str = Field(default='admin', description='来源标识')
    source_detail: str | None = Field(default=None, description='来源详情')
    remark: str | None = Field(default=None, description='备注')


class GetUserMembershipDetail(SchemaBase):
    """用户会员详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='记录 ID')
    user_id: int = Field(description='用户 ID')
    plan_id: int = Field(description='会员计划 ID')
    plan_name: str = Field(description='计划名称')
    level: int = Field(description='会员等级')
    valid_from: datetime | None = Field(default=None, description='有效期开始')
    valid_to: datetime | None = Field(default=None, description='有效期结束')
    source: str = Field(description='来源')
    status: int = Field(description='状态')
    remark: str | None = Field(default=None, description='备注')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(default=None, description='更新时间')


class GetUserMembershipBrief(SchemaBase):
    """用户会员简要"""

    model_config = ConfigDict(from_attributes=True)

    plan_name: str = Field(description='计划名称')
    level: int = Field(description='会员等级')
    valid_from: datetime | None = Field(default=None, description='有效期开始')
    valid_to: datetime | None = Field(default=None, description='有效期结束')
    status: int = Field(description='状态')
