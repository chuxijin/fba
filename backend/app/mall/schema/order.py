#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase

# ===== enums =====
OrderStatus = Literal['pending', 'paid', 'cancelled', 'refunded', 'completed']
OrderType = Literal['normal', 'group_buy']


# ===== order =====
class CreateOrderParam(SchemaBase):
    """创建订单参数"""

    product_id: int = Field(gt=0, description='商品 ID')
    sku_id: int = Field(gt=0, description='SKU ID')
    quantity: int = Field(default=1, ge=1, description='购买数量')
    order_type: OrderType = Field(default='normal', description='订单类型')
    team_id: int | None = Field(None, gt=0, description='拼团团队 ID')
    activity_id: int | None = Field(None, gt=0, description='拼团活动 ID')
    remark: str | None = Field(None, max_length=512, description='订单备注')


class GetOrderListItem(SchemaBase):
    """订单列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='订单 ID')
    order_no: str = Field(description='订单号')
    user_id: int = Field(description='用户 ID')
    order_type: OrderType = Field(description='订单类型')
    product_id: int = Field(description='商品 ID')
    sku_id: int = Field(description='SKU ID')
    product_name: str = Field(description='商品名称')
    sku_name: str = Field(description='SKU 名称')
    quantity: int = Field(description='购买数量')
    unit_price: Decimal = Field(description='单价')
    total_amount: Decimal = Field(description='订单总额')
    paid_amount: Decimal = Field(description='已支付金额')
    status: OrderStatus = Field(description='订单状态')
    team_id: int | None = Field(None, description='拼团团队 ID')
    activity_id: int | None = Field(None, description='拼团活动 ID')
    created_time: datetime = Field(description='创建时间')


class GetOrderDetail(GetOrderListItem):
    """订单详情"""

    remark: str | None = Field(None, description='订单备注')
    extra_data: dict[str, Any] | None = Field(None, description='扩展数据')
    paid_time: datetime | None = Field(None, description='支付时间')
    cancelled_time: datetime | None = Field(None, description='取消时间')
    refunded_time: datetime | None = Field(None, description='退款时间')
    completed_time: datetime | None = Field(None, description='完成时间')
    updated_time: datetime | None = Field(None, description='更新时间')
