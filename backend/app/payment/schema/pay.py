#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase

PayTransactionStatus = Literal['pending', 'paid', 'refund_pending', 'refunded', 'closed']
PayType = Literal['jsapi', 'h5', 'virtual']
PayOrderStatus = Literal['pending', 'paid', 'refund_pending', 'refunded', 'closed']
PayOrderFulfillStatus = Literal['pending', 'fulfilled', 'failed', 'revoked']


class CreatePrepayParam(SchemaBase):
    """创建预支付参数"""

    order_no: str = Field(max_length=64, description='业务订单号')
    biz_type: str = Field(max_length=32, description='业务类型')
    pay_type: PayType = Field(description='支付方式')
    amount: Decimal = Field(gt=0, description='支付金额（元）')
    product_name: str = Field(max_length=256, description='商品描述')
    user_id: int = Field(gt=0, description='支付用户 ID')
    openid: str | None = Field(None, description='用户 openid（JSAPI 必传）')
    session_key: str | None = Field(None, description='微信 session_key（虚拟支付必传）')
    product_id: str | None = Field(None, max_length=128, description='虚拟支付道具 ID')
    payer_ip: str | None = Field(None, description='用户 IP（H5 必传）')
    env: int = Field(default=0, description='虚拟支付环境：0 现网，1 沙箱')


class PrepayResult(SchemaBase):
    """预下单结果"""

    pay_params: dict[str, Any] = Field(description='前端拉起支付所需参数')
    transaction_no: str = Field(description='内部交易号')


class RefundParam(SchemaBase):
    """退款参数"""

    order_no: str = Field(max_length=64, description='业务订单号')
    refund_amount: Decimal | None = Field(None, gt=0, description='退款金额（默认全额退款）')
    reason: str | None = Field(None, max_length=256, description='退款原因')


class RefundResult(SchemaBase):
    """退款结果"""

    refund_no: str = Field(description='退款单号')
    status: str = Field(description='退款状态')


class SubscriptionPrepayParam(SchemaBase):
    """订阅预下单参数"""

    template_code: str = Field(max_length=64, description='订阅模板编码')
    wx_code: str = Field(description='微信小程序登录 code')
    pay_type: Literal['virtual'] = Field(default='virtual', description='支付方式')
    env: int = Field(default=0, description='虚拟支付环境：0 现网，1 沙箱')


class SubscriptionPrepayResult(SchemaBase):
    """订阅预下单结果"""

    order_no: str = Field(description='业务订单号')
    transaction_no: str = Field(description='内部交易号')
    pay_params: dict[str, Any] = Field(description='前端拉起支付所需参数')


class SubscriptionPaymentConfirmParam(SchemaBase):
    """订阅支付确认参数"""

    order_no: str = Field(max_length=64, description='业务订单号')
    wx_code: str | None = Field(default=None, description='微信小程序登录 code')


class PaymentConfirmResult(SchemaBase):
    """支付确认结果"""

    order_no: str = Field(description='业务订单号')
    status: PayOrderStatus = Field(description='支付状态')
    fulfill_status: PayOrderFulfillStatus = Field(description='发放状态')
    paid: bool = Field(description='是否已支付')
    fulfilled: bool = Field(description='是否已发放权益')


class PayOrderListItem(SchemaBase):
    """支付业务订单列表项"""

    model_config = ConfigDict(from_attributes=True)

    order_no: str = Field(description='业务订单号')
    biz_type: str = Field(description='业务类型')
    item_code: str = Field(description='购买项编码')
    item_name: str = Field(description='购买项名称')
    amount: Decimal = Field(description='支付金额')
    pay_type: str = Field(description='支付方式')
    status: PayOrderStatus = Field(description='支付状态')
    fulfill_status: PayOrderFulfillStatus = Field(description='发放状态')
    trade_no: str | None = Field(default=None, description='第三方交易号')
    transaction_no: str | None = Field(default=None, description='最近内部交易号')
    created_time: datetime = Field(description='创建时间')
    paid_time: datetime | None = Field(default=None, description='支付成功时间')
    fulfilled_time: datetime | None = Field(default=None, description='权益发放时间')
    refunded_time: datetime | None = Field(default=None, description='退款成功时间')
    closed_time: datetime | None = Field(default=None, description='关闭时间')
