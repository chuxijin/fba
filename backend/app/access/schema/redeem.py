#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import Field

from backend.common.schema import SchemaBase


class CreateRedeemBatchParam(SchemaBase):
    """创建兑换批次"""

    app_id: str = Field(default='fba-mini', max_length=32, description='应用 ID')
    name: str = Field(max_length=128, description='批次名称')
    template_code: str = Field(max_length=64, description='订阅模板编码')
    total_count: int = Field(default=0, ge=0, le=1000000, description='订单容量, 0 表示不限')
    valid_from: datetime | None = Field(default=None, description='有效期开始')
    valid_to: datetime | None = Field(default=None, description='有效期结束')
    max_use_per_code: int = Field(default=1, gt=0, le=100, description='单码最大使用次数')


class UpdateRedeemBatchParam(SchemaBase):
    """更新兑换批次"""

    name: str | None = Field(default=None, max_length=128, description='批次名称')
    template_code: str | None = Field(default=None, max_length=64, description='订阅模板编码')
    total_count: int | None = Field(default=None, ge=0, le=1000000, description='订单容量, 0 表示不限')
    valid_from: datetime | None = Field(default=None, description='有效期开始')
    valid_to: datetime | None = Field(default=None, description='有效期结束')
    max_use_per_code: int | None = Field(default=None, gt=0, le=100, description='单码最大使用次数')
    status: int | None = Field(default=None, ge=0, le=1, description='状态')


class GetRedeemBatchDetail(SchemaBase):
    """兑换批次详情"""

    id: int = Field(description='批次 ID')
    app_id: str = Field(description='应用 ID')
    batch_no: str = Field(description='批次编号')
    name: str = Field(description='批次名称')
    reward_type: str = Field(description='权益类型')
    reward_data: dict = Field(description='权益数据')
    template_code: str | None = Field(default=None, description='订阅模板编码')
    total_count: int = Field(description='订单容量')
    used_count: int = Field(description='已写入订单数')
    valid_from: datetime | None = Field(default=None, description='有效期开始')
    valid_to: datetime | None = Field(default=None, description='有效期结束')
    max_use_per_code: int = Field(description='单码最大使用次数')
    status: int = Field(description='状态')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(default=None, description='更新时间')


class AgisoBatchRuleParam(SchemaBase):
    """阿奇索批次规则"""

    platform: str = Field(max_length=50, description='平台')
    keyword: str = Field(max_length=128, description='商品关键词')
    batch_id: int = Field(gt=0, description='激活码批次 ID')


class SetAgisoBatchRulesParam(SchemaBase):
    """设置阿奇索批次规则"""

    rules: list[AgisoBatchRuleParam] = Field(default_factory=list, description='匹配规则')
