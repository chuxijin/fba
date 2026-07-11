#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.access.constants import SubscriptionSource
from backend.app.access.model.subscription import Subscription
from backend.app.access.service.subscription_service import subscription_service
from backend.app.payment.crud.crud_pay_order import pay_order_dao
from backend.common.log import log
from backend.common.payment import get_provider
from backend.utils.timezone import timezone


class SubscriptionPaymentNotifier:
    """订阅支付通知处理器"""

    @staticmethod
    async def _existing_subscription(db: AsyncSession, *, user_id: int, order_no: str) -> Subscription | None:
        """
        查询支付订单是否已发放订阅

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param order_no: 业务订单号
        :return:
        """
        stmt = select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.source == SubscriptionSource.ORDER,
            Subscription.source_ref == order_no,
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def on_payment_success(
        self, *, db: AsyncSession, order_no: str, trade_no: str, paid_amount: Decimal
    ) -> None:
        """
        支付成功后开通订阅

        :param db: 数据库会话
        :param order_no: 业务订单号
        :param trade_no: 第三方交易号
        :param paid_amount: 已支付金额
        :return:
        """
        order = await pay_order_dao.get_by_order_no(db, order_no)
        if not order:
            log.warning(f'订阅支付回调未找到业务订单: order_no={order_no}')
            return
        if order.biz_type != 'subscription_template':
            return
        if order.fulfill_status == 'fulfilled':
            return

        existing = await self._existing_subscription(db, user_id=order.user_id, order_no=order.order_no)
        if existing is None:
            existing = await subscription_service.create_from_template(
                db,
                user_id=order.user_id,
                template_code=order.item_code,
                source=SubscriptionSource.ORDER,
                source_ref=order.order_no,
            )

        await pay_order_dao.update_model(
            db,
            order.id,
            {
                'fulfill_status': 'fulfilled',
                'fulfilled_time': timezone.now(),
                'extra_data': {
                    **(order.extra_data or {}),
                    'subscription_id': existing.id,
                    'trade_no': trade_no,
                    'paid_amount': str(paid_amount),
                },
            },
        )

        if order.pay_type == 'virtual':
            try:
                provider = get_provider('virtual')
                notify = getattr(provider, 'notify_provide_goods', None)
                if notify:
                    env = int((order.extra_data or {}).get('env') or 0)
                    await notify(order_no=order.order_no, env=env)
            except Exception as e:
                log.error(f'虚拟支付发货通知失败，已保留权益发放结果: order_no={order.order_no}, error={e}')

    async def on_refund_success(self, *, db: AsyncSession, order_no: str) -> None:
        """
        退款成功后撤销订阅

        :param db: 数据库会话
        :param order_no: 业务订单号
        :return:
        """
        order = await pay_order_dao.get_by_order_no(db, order_no)
        if not order or order.biz_type != 'subscription_template':
            return

        await subscription_service.revoke_by_source(
            db,
            user_id=order.user_id,
            source=SubscriptionSource.ORDER,
            source_ref=order.order_no,
            reason='支付退款撤销',
        )
        await pay_order_dao.update_model(
            db,
            order.id,
            {'fulfill_status': 'revoked', 'refunded_time': timezone.now()},
        )

    async def on_payment_closed(self, *, db: AsyncSession, order_no: str) -> None:
        """
        支付关闭回调

        :param db: 数据库会话
        :param order_no: 业务订单号
        :return:
        """
        order = await pay_order_dao.get_by_order_no(db, order_no)
        if not order:
            return
        await pay_order_dao.update_model(db, order.id, {'status': 'closed', 'closed_time': timezone.now()})


subscription_payment_notifier: SubscriptionPaymentNotifier = SubscriptionPaymentNotifier()
