#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.app.access.constants import LedgerOperation
from backend.common.schema import SchemaBase


class CreditQuotaParam(SchemaBase):
    """配额入账(增加余额)"""

    user_id: int = Field(description='用户 ID')
    entitlement_code: str = Field(description='权益编码')
    amount: int = Field(gt=0, description='入账数量')
    cycle_type: str = Field(description='周期类型')
    cycle_key: str | None = Field(default=None, description='周期键, 空则按当前时间算')
    scope_key: str = Field(default='global', description='业务范围键')
    source: str = Field(max_length=32, description='来源标识')
    source_ref: str | None = Field(default=None, max_length=128, description='来源引用')
    idempotency_key: str | None = Field(default=None, max_length=128, description='幂等键')
    reason: str | None = Field(default=None, max_length=256, description='原因')


class DebitQuotaParam(SchemaBase):
    """配额扣减"""

    user_id: int = Field(description='用户 ID')
    entitlement_code: str = Field(description='权益编码')
    amount: int = Field(gt=0, description='扣减数量')
    cycle_type: str = Field(description='周期类型')
    cycle_key: str | None = Field(default=None, description='周期键, 空则按当前时间算')
    scope_key: str = Field(default='global', description='业务范围键')
    source: str = Field(max_length=32, description='来源标识')
    source_ref: str | None = Field(default=None, max_length=128, description='来源引用')
    idempotency_key: str | None = Field(default=None, max_length=128, description='幂等键')
    reason: str | None = Field(default=None, max_length=256, description='原因')


class RefundQuotaParam(SchemaBase):
    """配额回滚(用于失败补偿)"""

    user_id: int = Field(description='用户 ID')
    entitlement_code: str = Field(description='权益编码')
    amount: int = Field(gt=0, description='回滚数量')
    cycle_type: str = Field(description='周期类型')
    cycle_key: str | None = Field(default=None, description='周期键')
    scope_key: str = Field(default='global', description='业务范围键')
    source: str = Field(max_length=32, description='来源标识')
    source_ref: str = Field(max_length=128, description='来源引用(必填,关联原扣减)')
    idempotency_key: str = Field(max_length=128, description='幂等键(必填)')
    reason: str | None = Field(default=None, max_length=256, description='原因')


class GetLedgerDetail(SchemaBase):
    """账本流水详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='流水 ID')
    user_id: int = Field(description='用户 ID')
    entitlement_code: str = Field(description='权益编码')
    scope_key: str = Field(description='业务范围键')
    cycle_type: str = Field(description='周期类型')
    cycle_key: str = Field(description='周期键')
    operation: LedgerOperation = Field(description='操作类型')
    amount: int = Field(description='变动数量')
    balance_after: int = Field(description='操作后余额')
    source: str = Field(description='来源标识')
    source_ref: str | None = Field(description='来源引用')
    reason: str | None = Field(description='原因')
    occurred_at: datetime = Field(description='发生时间')


class GetQuotaBalance(SchemaBase):
    """配额余额"""

    user_id: int = Field(description='用户 ID')
    entitlement_code: str = Field(description='权益编码')
    scope_key: str = Field(description='业务范围键')
    cycle_type: str = Field(description='周期类型')
    cycle_key: str = Field(description='周期键')
    balance: int = Field(description='当前余额')
    limit: int | None = Field(default=None, description='上限')
    used: int = Field(description='已用')
