#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal, Self

from pydantic import ConfigDict, Field, model_validator

from backend.common.schema import SchemaBase

PayTransactionStatus = Literal['pending', 'paid', 'refund_pending', 'refunded', 'closed']
PayType = Literal['jsapi', 'h5', 'virtual', 'hupijiao']
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
    wx_code: str | None = Field(default=None, description='微信小程序登录 code（虚拟支付必传）')
    pay_type: Literal['virtual', 'hupijiao'] = Field(default='virtual', description='支付方式')
    env: Literal[0, 1] = Field(default=0, description='虚拟支付环境：0 现网，1 沙箱；虎皮椒仅支持 0')

    @model_validator(mode='after')
    def validate_channel_params(self) -> Self:
        """按选择的支付方式校验参数。"""
        if self.pay_type == 'virtual' and not (self.wx_code and self.wx_code.strip()):
            raise ValueError('虚拟支付必须提供微信小程序登录 code')
        if self.pay_type == 'hupijiao' and self.env != 0:
            raise ValueError('虎皮椒不支持微信虚拟支付沙箱环境')
        return self


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
    group_buy: dict[str, Any] | None = Field(default=None, description='拼团进度与奖励状态')


class PayOrderListItem(SchemaBase):
    """支付业务订单列表项"""

    model_config = ConfigDict(from_attributes=True)

    order_no: str = Field(description='业务订单号')
    biz_type: str = Field(description='业务类型')
    purchase_mode: Literal['direct', 'group_buy'] = 'direct'
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
