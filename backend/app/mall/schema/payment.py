#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from decimal import Decimal

from pydantic import Field

from backend.common.schema import SchemaBase


class PrepayParam(SchemaBase):
    """预下单参数"""

    order_id: int = Field(gt=0, description='订单 ID')
    pay_type: str = Field(description='支付方式(jsapi/h5)')
    openid: str | None = Field(None, description='用户 openid（JSAPI 必传）')
    payer_ip: str | None = Field(None, description='用户 IP（H5 必传）')


class PrepayResult(SchemaBase):
    """预下单结果"""

    pay_params: dict = Field(description='前端拉起支付所需参数')


class RefundParam(SchemaBase):
    """退款参数"""

    order_id: int = Field(gt=0, description='订单 ID')
    refund_amount: Decimal | None = Field(None, gt=0, description='退款金额（默认全额退款）')
    reason: str | None = Field(None, max_length=256, description='退款原因')


class RefundResult(SchemaBase):
    """退款结果"""

    refund_id: str = Field(description='退款单号')
    status: str = Field(description='退款状态')
