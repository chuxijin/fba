#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date
from typing import Any, Literal, Self

from pydantic import Field, model_validator

from backend.app.payment.schema.pay import PayOrderListItem
from backend.common.schema import SchemaBase


class MyOrderQuery(SchemaBase):
    """用户订单查询；日期按服务端配置时区包含起止日。"""

    status: Literal['all', 'pending', 'paid', 'refund', 'refund_pending', 'refunded', 'closed'] = 'all'
    keyword: str | None = Field(default=None, max_length=128)
    biz_type: str | None = Field(default=None, max_length=32)
    pay_type: str | None = Field(default=None, max_length=16)
    created_from: date | None = None
    created_to: date | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)

    @model_validator(mode='after')
    def validate_dates(self) -> Self:
        if self.created_from and self.created_to and self.created_from > self.created_to:
            raise ValueError('开始日期不能晚于结束日期')
        if self.created_to == date.max:
            raise ValueError('结束日期超出范围')
        return self


class MyOrderItem(PayOrderListItem):
    """只暴露允许的快照字段，不返回 openid、渠道签名等扩展信息。"""

    tier_code: str | None = None
    can_remove: bool = False
    can_close: bool = False
    close_kind: Literal['local', 'remote'] = 'local'
    group_buy: dict[str, Any] | None = None


class MyOrderPage(SchemaBase):
    items: list[MyOrderItem]
    total: int
    page: int
    page_size: int
    biz_types: list[str]
    pay_types: list[str]


class MyOrderActionParam(SchemaBase):
    wx_code: str | None = Field(default=None, max_length=256)
