#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from decimal import Decimal
from typing import Protocol, runtime_checkable

from sqlalchemy.ext.asyncio import AsyncSession


@runtime_checkable
class PaymentNotifier(Protocol):
    """支付结果通知接口

    业务模块（如 mall）实现此接口，并通过 register_notifier() 注册。
    payment 模块在支付状态变更时回调对应方法，实现与业务模块的解耦。
    """

    async def on_payment_success(
        self, *, db: AsyncSession, order_no: str, trade_no: str, paid_amount: Decimal
    ) -> None:
        """支付成功回调"""
        ...

    async def on_refund_success(self, *, db: AsyncSession, order_no: str) -> None:
        """退款成功回调"""
        ...

    async def on_payment_closed(self, *, db: AsyncSession, order_no: str) -> None:
        """支付关闭回调"""
        ...
