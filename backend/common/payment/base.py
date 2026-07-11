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
    async def query(self, *, order_no: str, **kwargs) -> dict:
        """
        查询订单支付状态

        :param order_no: 商户订单号
        :return:
        """

    @abstractmethod
    async def close(self, *, order_no: str, **kwargs) -> None:
        """
        关闭订单

        :param order_no: 商户订单号
        :return:
        """

    @abstractmethod
    async def refund(
        self, *, order_no: str, refund_no: str, total_fee: int, refund_fee: int, reason: str | None = None, **kwargs
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

    def normalize_callback_data(self, callback_data: dict, *, event: str = 'payment') -> dict:
        """
        将原始回调数据归一化为标准格式

        标准字段: order_no, trade_no, trade_state, refund_status

        :param callback_data: 原始回调数据
        :param event: 事件类型 (payment / refund)
        :return:
        """
        return callback_data

    def normalize_query_data(self, query_data: dict, *, order_no: str) -> dict:
        """
        将查询结果归一化为标准格式

        :param query_data: 原始查询结果
        :param order_no: 业务订单号
        :return:
        """
        return query_data
