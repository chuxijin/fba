#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.mall.crud.crud_order import order_dao
from backend.common.log import log
from backend.utils.timezone import timezone


class MallPaymentNotifier:
    """商城支付通知处理器"""

    @staticmethod
    async def on_payment_success(*, db: AsyncSession, order_no: str, trade_no: str, paid_amount: Decimal) -> None:
        """
        支付成功 -> 更新订单状态

        :param db: 数据库会话
        :param order_no: 订单号
        :param trade_no: 第三方交易号
        :param paid_amount: 已支付金额
        :return:
        """
        order = await order_dao.get_by_order_no(db, order_no)
        if not order:
            log.error(f'支付回调订单不存在: order_no={order_no}')
            return
        if order.status == 'paid':
            return
        now = timezone.now()
        await order_dao.update_model(
            db,
            order.id,
            {
                'status': 'paid',
                'paid_amount': paid_amount,
                'paid_time': now,
                'trade_no': trade_no,
            },
        )
        # TODO: 扣减库存 (stock -= quantity, sales_count += quantity)

    @staticmethod
    async def on_refund_success(*, db: AsyncSession, order_no: str) -> None:
        """
        退款成功 -> 更新订单状态

        :param db: 数据库会话
        :param order_no: 订单号
        :return:
        """
        order = await order_dao.get_by_order_no(db, order_no)
        if not order:
            log.error(f'退款回调订单不存在: order_no={order_no}')
            return
        now = timezone.now()
        await order_dao.update_model(
            db,
            order.id,
            {'status': 'refunded', 'refunded_time': now},
        )

    @staticmethod
    async def on_payment_closed(*, db: AsyncSession, order_no: str) -> None:
        """
        支付关闭回调

        :param db: 数据库会话
        :param order_no: 订单号
        :return:
        """
        pass


mall_payment_notifier: MallPaymentNotifier = MallPaymentNotifier()
