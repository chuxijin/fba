#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from abc import ABC, abstractmethod


class PaymentProvider(ABC):
    """支付渠道抽象基类"""

    @abstractmethod
    async def prepay(self, *, order_no: str, total_fee: int, description: str, **kwargs) -> dict:
        """
        预下单

        :param order_no: 商户订单号
        :param total_fee: 总金额（单位：分）
        :param description: 商品描述
        :return:
        """

    @abstractmethod
    async def query(self, *, order_no: str) -> dict:
        """
        查询订单支付状态

        :param order_no: 商户订单号
        :return:
        """

    @abstractmethod
    async def close(self, *, order_no: str) -> None:
        """
        关闭订单

        :param order_no: 商户订单号
        :return:
        """

    @abstractmethod
    async def refund(
        self, *, order_no: str, refund_no: str, total_fee: int, refund_fee: int, reason: str | None = None
    ) -> dict:
        """
        申请退款

        :param order_no: 商户订单号
        :param refund_no: 商户退款单号
        :param total_fee: 原订单金额（单位：分）
        :param refund_fee: 退款金额（单位：分）
        :param reason: 退款原因
        :return:
        """

    @abstractmethod
    def decrypt_callback(self, *, headers: dict, body: bytes) -> dict:
        """
        验签并解密回调通知

        :param headers: HTTP 请求头
        :param body: 请求体原始字节
        :return:
        """
