#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field

from backend.app.access.constants import SubscriptionSource, SubscriptionStatus
from backend.app.access.schema.base import TimePeriodInput, TimePeriodOutput
from backend.common.schema import SchemaBase


class CreateSubscriptionParam(SchemaBase):
    """创建用户订阅(管理端/迁移用)"""

    user_id: int = Field(description='用户 ID')
    template_code: str = Field(description='模板编码')
    valid_period: TimePeriodInput = Field(description='有效时间段')
    source: SubscriptionSource = Field(description='来源')
    source_ref: str | None = Field(default=None, max_length=128, description='来源引用')
    parent_subscription_id: int | None = Field(default=None, description='父订阅 ID')
    metadata: dict[str, Any] = Field(default_factory=dict, description='扩展元数据')


class CancelSubscriptionParam(SchemaBase):
    """取消用户订阅"""

    cancel_reason: str = Field(max_length=256, description='取消原因')


class SubscriptionQueryParam(SchemaBase):
    """订阅查询"""

    user_id: int | None = Field(default=None, description='用户 ID')
    template_code: str | None = Field(default=None, description='模板编码')
    status: SubscriptionStatus | None = Field(default=None, description='状态')
    source: SubscriptionSource | None = Field(default=None, description='来源')
    only_active: bool = Field(default=False, description='仅当前有效')


class GetSubscriptionDetail(SchemaBase):
    """订阅详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='订阅 ID')
    user_id: int = Field(description='用户 ID')
    template_id: int = Field(description='模板 ID')
    valid_period: TimePeriodOutput = Field(description='有效时间段')
    status: SubscriptionStatus = Field(description='状态')
    source: SubscriptionSource = Field(description='来源')
    source_ref: str | None = Field(description='来源引用')
    parent_subscription_id: int | None = Field(description='父订阅 ID')
    cancel_reason: str | None = Field(description='取消原因')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(default=None, description='更新时间')
    username: str | None = Field(default=None, description='用户名')
    nickname: str | None = Field(default=None, description='用户昵称')
    template_code: str | None = Field(default=None, description='模板编码')
    template_name: str | None = Field(default=None, description='模板名称')
    valid_from: datetime | None = Field(default=None, description='生效时间')
    valid_to: datetime | None = Field(default=None, description='到期时间')


class GetMySubscription(SchemaBase):
    """我的订阅项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='订阅 ID')
    template_code: str = Field(description='模板编码')
    template_name: str = Field(description='模板名称')
    pack_code: str | None = Field(default=None, description='首个权益包编码')
    pack_codes: list[str] = Field(default_factory=list, description='关联权益包编码列表')
    domain_codes: list[str] = Field(default_factory=list, description='关联领域编码')
    cover_image: str | None = Field(default=None, description='封面图')
    valid_period: TimePeriodOutput = Field(description='有效时间段')
    valid_from: datetime = Field(description='开始时间')
    valid_to: datetime | None = Field(default=None, description='结束时间')
    status: SubscriptionStatus = Field(description='状态')
    created_time: datetime = Field(description='创建时间')


class GetMySubscriptionLedger(SchemaBase):
    """我的订阅流水"""

    id: int = Field(description='订阅 ID')
    template_code: str = Field(description='模板编码')
    template_name: str = Field(description='模板名称')
    op_type: str = Field(description='操作类型')
    days: int = Field(description='订阅天数')
    source: str = Field(description='来源')
    valid_to_after: datetime | None = Field(default=None, description='操作后到期时间')
    created_time: datetime = Field(description='创建时间')
