#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from decimal import Decimal

from pydantic import Field

from backend.common.schema import SchemaBase


class CreateOrderParam(SchemaBase):
    """创建订单参数"""

    package_id: int = Field(description='套餐ID')
    device_id: int | None = Field(None, description='设备ID')
    user_id: int | None = Field(None, description='用户ID')
    username: str | None = Field(None, description='用户名')
    contact_info: str | None = Field(None, description='联系方式')
    remark: str | None = Field(None, description='备注')


class UpdateOrderParam(SchemaBase):
    """更新订单参数"""

    payment_method: str | None = Field(None, description='支付方式')
    payment_status: int | None = Field(None, description='支付状态')
    order_status: int | None = Field(None, description='订单状态')
    paid_amount: Decimal | None = Field(None, description='已支付金额')
    remark: str | None = Field(None, description='备注')


class GetOrderDetail(SchemaBase):
    """订单详情"""

    id: int = Field(description='订单ID')
    order_no: str = Field(description='订单号')
    package_id: int = Field(description='套餐ID')
    device_id: int | None = Field(description='设备ID')
    user_id: int | None = Field(description='用户ID')
    username: str | None = Field(description='用户名')
    contact_info: str | None = Field(description='联系方式')
    total_amount: Decimal = Field(description='订单总金额')
    paid_amount: Decimal = Field(description='已支付金额')
    payment_method: str | None = Field(description='支付方式')
    payment_status: int = Field(description='支付状态')
    order_status: int = Field(description='订单状态')
    remark: str | None = Field(description='备注')
    created_time: datetime = Field(description='创建时间')
    paid_time: datetime | None = Field(description='支付时间')
    completed_time: datetime | None = Field(description='完成时间')