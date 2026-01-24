#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pydantic import BaseModel, Field


class AgisoPaymentPushData(BaseModel):
    """
    阿奇索支付推送数据

    :param Tid: 订单编号
    :param Status: 订单状态
    :param SellerNick: 卖家昵称
    :param SellerOpenUid: 卖家ID
    :param BuyerNick: 买家昵称
    :param BuyerOpenUid: 买家ID
    :param Payment: 支付金额
    :param Type: 交易类型
    """

    Tid: int | str = Field(description='订单编号')
    Status: str = Field(description='订单状态')
    SellerNick: str = Field(description='卖家昵称')
    SellerOpenUid: str | None = Field(default=None, description='卖家ID')
    BuyerNick: str = Field(description='买家昵称')
    BuyerOpenUid: str | None = Field(default=None, description='买家ID')
    Payment: str = Field(description='支付金额')
    Type: str = Field(description='交易类型')


class AgisoDeliveryCard(BaseModel):
    """发卡信息"""

    card_no: str = Field(description='卡号')
    card_pwd: str | None = Field(default=None, description='卡密')
    card_value: str | None = Field(default=None, description='卡面额')


class AgisoDeliveryPushData(BaseModel):
    """
    阿奇索发卡推送数据

    :param Tid: 订单编号
    :param Status: 订单状态
    :param BuyerNick: 买家昵称
    :param BuyerOpenUid: 买家ID
    :param Cards: 卡密列表
    """

    Tid: int | str = Field(description='订单编号')
    Status: str = Field(description='订单状态')
    BuyerNick: str = Field(description='买家昵称')
    BuyerOpenUid: str | None = Field(default=None, description='买家ID')
    Cards: list[AgisoDeliveryCard] = Field(default_factory=list, description='卡密列表')
