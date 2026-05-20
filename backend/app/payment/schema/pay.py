#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from decimal import Decimal
from typing import Literal

from pydantic import Field

from backend.common.schema import SchemaBase

PayTransactionStatus = Literal['pending', 'paid', 'refund_pending', 'refunded', 'closed']
PayType = Literal['jsapi', 'h5', 'virtual']


class CreatePrepayParam(SchemaBase):
    """创建预支付参数"""

    order_no: str = Field(max_length=64, description='业务订单号')
    biz_type: str = Field(default='mall_order', max_length=32, description='业务类型')
    pay_type: PayType = Field(description='支付方式')
    amount: Decimal = Field(gt=0, description='支付金额（元）')
    product_name: str = Field(max_length=256, description='商品描述')
    user_id: int = Field(gt=0, description='支付用户 ID')
    openid: str | None = Field(None, description='用户 openid（JSAPI 必传）')
    payer_ip: str | None = Field(None, description='用户 IP（H5 必传）')


class PrepayResult(SchemaBase):
    """预下单结果"""

    pay_params: dict = Field(description='前端拉起支付所需参数')
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


class MallPrepayParam(SchemaBase):
    """商城预下单参数"""

    order_id: int = Field(gt=0, description='订单 ID')
    pay_type: PayType = Field(description='支付方式')
    openid: str | None = Field(None, description='用户 openid（JSAPI 必传）')
    payer_ip: str | None = Field(None, description='用户 IP（H5 必传）')


class MallRefundParam(SchemaBase):
    """商城退款参数"""

    order_id: int = Field(gt=0, description='订单 ID')
    refund_amount: Decimal | None = Field(None, gt=0, description='退款金额（默认全额退款）')
    reason: str | None = Field(None, max_length=256, description='退款原因')
