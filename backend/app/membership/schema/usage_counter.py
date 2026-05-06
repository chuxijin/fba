#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class CreateMembershipUsageCounterParam(SchemaBase):
    """创建用量计数"""

    user_id: int = Field(description='用户 ID')
    entitlement_code: str = Field(min_length=1, max_length=64, description='权益编码')
    scope_key: str = Field(default='default', min_length=1, max_length=64, description='业务范围键')
    cycle_type: str = Field(default='monthly', min_length=1, max_length=16, description='周期类型')
    cycle_key: str = Field(default='lifetime', min_length=1, max_length=32, description='周期键')
    used_value: int = Field(default=0, ge=0, description='已使用数量')
    reserved_value: int = Field(default=0, ge=0, description='预留数量')
    limit_value: int | None = Field(default=None, ge=0, description='周期额度上限')
    last_source: str | None = Field(default=None, max_length=32, description='最后来源')
    last_source_key: str | None = Field(default=None, max_length=128, description='最后来源业务键')
    remark: str | None = Field(default=None, description='备注')


class UpdateMembershipUsageCounterParam(SchemaBase):
    """更新用量计数"""

    used_value: int | None = Field(default=None, ge=0, description='已使用数量')
    reserved_value: int | None = Field(default=None, ge=0, description='预留数量')
    limit_value: int | None = Field(default=None, ge=0, description='周期额度上限')
    last_source: str | None = Field(default=None, max_length=32, description='最后来源')
    last_source_key: str | None = Field(default=None, max_length=128, description='最后来源业务键')
    remark: str | None = Field(default=None, description='备注')


class GetMembershipUsageCounterDetail(SchemaBase):
    """用量计数详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='计数 ID')
    user_id: int = Field(description='用户 ID')
    entitlement_code: str = Field(description='权益编码')
    scope_key: str = Field(description='业务范围键')
    cycle_type: str = Field(description='周期类型')
    cycle_key: str = Field(description='周期键')
    used_value: int = Field(description='已使用数量')
    reserved_value: int = Field(description='预留数量')
    limit_value: int | None = Field(default=None, description='周期额度上限')
    last_used_time: datetime | None = Field(default=None, description='最后使用时间')
    last_source: str | None = Field(default=None, description='最后来源')
    last_source_key: str | None = Field(default=None, description='最后来源业务键')
    remark: str | None = Field(default=None, description='备注')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(default=None, description='更新时间')
