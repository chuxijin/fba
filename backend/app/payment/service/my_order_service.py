#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.payment.crud.crud_pay_order import pay_order_dao
from backend.app.payment.crud.crud_pay_transaction import pay_transaction_dao
from backend.app.payment.model.pay_order import PayOrder
from backend.app.payment.schema.my_orders import MyOrderItem, MyOrderPage, MyOrderQuery
from backend.app.payment.schema.pay import SubscriptionPaymentConfirmParam
from backend.app.payment.service.pay_order_service import pay_order_service
from backend.app.payment.service.pay_service import pay_service
from backend.common.exception import errors
from backend.common.payment.dispatcher import get_provider
from backend.utils.timezone import timezone


class MyOrderService:
    """当前用户的订单查询与列表管理；不物理删除支付记录。"""

    @staticmethod
    def present(order: PayOrder) -> MyOrderItem:
        item = MyOrderItem.model_validate(order)
        tier = str((order.extra_data or {}).get('tier_code') or '').upper()
        item.tier_code = tier if tier in ('FREE', 'VIP', 'SVIP') else None
        item.can_remove = order.status in ('closed', 'refunded')
        item.can_close = order.status == 'pending'
        item.close_kind = 'remote' if order.pay_type in ('jsapi', 'h5') else 'local'
        return item

    @staticmethod
    async def owned(db: AsyncSession, user_id: int, order_no: str, *, for_update: bool = False) -> PayOrder:
        order = await pay_order_dao.get_by_order_no(db, order_no, for_update=for_update)
        if not order or order.user_id != user_id or getattr(order, 'deleted', 0) != 0:
            raise errors.NotFoundError(msg='订单不存在')
        return order

    @staticmethod
    async def detail(db: AsyncSession, user_id: int, order_no: str) -> MyOrderItem:
        order = await MyOrderService.owned(db, user_id, order_no)
        item = MyOrderService.present(order)
        if getattr(order, 'purchase_mode', 'direct') == 'group_buy':
            from backend.app.payment.service.group_buy_service import group_buy_service

            summary = await group_buy_service.summary(db, order)
            item.group_buy = summary.model_dump() if summary else None
        return item

    @staticmethod
    async def page(db: AsyncSession, user_id: int, query: MyOrderQuery) -> MyOrderPage:
        rows, total = await pay_order_dao.get_user_page(db, user_id, query)
        biz_types, pay_types = await pay_order_dao.get_user_filter_options(db, user_id)
        items = [MyOrderService.present(row) for row in rows]
        for row, item in zip(rows, items, strict=True):
            if getattr(row, 'purchase_mode', 'direct') == 'group_buy':
                from backend.app.payment.service.group_buy_service import group_buy_service

                summary = await group_buy_service.summary(db, row)
                item.group_buy = summary.model_dump() if summary else None
        return MyOrderPage(
            items=items,
            total=total,
            page=query.page,
            page_size=query.page_size,
            biz_types=biz_types,
            pay_types=pay_types,
        )

    @staticmethod
    async def remove(db: AsyncSession, user_id: int, order_no: str) -> None:
        order = await MyOrderService.owned(db, user_id, order_no, for_update=True)
        if order.status not in ('closed', 'refunded'):
            raise errors.RequestError(msg='仅已关闭或已退款的订单可以删除记录')
        if order.user_hidden_at is None:
            await pay_order_dao.update_model(db, order.id, {'user_hidden_at': timezone.now()})

    @staticmethod
    async def refresh(db: AsyncSession, user_id: int, order_no: str, wx_code: str | None = None) -> MyOrderItem:
        order = await MyOrderService.owned(db, user_id, order_no)
        if order.status not in ('refund_pending', 'refunded'):
            if order.biz_type == 'subscription_template':
                await pay_order_service.confirm_subscription_payment(
                    db=db, user_id=user_id, obj=SubscriptionPaymentConfirmParam(order_no=order_no, wx_code=wx_code)
                )
            else:
                await pay_service.sync_payment_status(
                    db=db, user_id=user_id, order_no=order_no, openid=(order.extra_data or {}).get('openid')
                )
        current = await MyOrderService.owned(db, user_id, order_no)
        item = MyOrderService.present(current)
        if getattr(current, 'purchase_mode', 'direct') == 'group_buy':
            from backend.app.payment.service.group_buy_service import group_buy_service

            summary = await group_buy_service.summary(db, current)
            item.group_buy = summary.model_dump() if summary else None
        return item

    @staticmethod
    async def close(db: AsyncSession, user_id: int, order_no: str, wx_code: str | None = None) -> MyOrderItem:
        order = await MyOrderService.owned(db, user_id, order_no)
        if order.status == 'closed':
            return MyOrderService.present(order)
        if order.status != 'pending':
            raise errors.RequestError(msg='仅待支付订单可以关闭')
        txn = await pay_transaction_dao.get_by_order_no(db, order_no)
        if txn:
            # 查询失败时不假装取消成功；若已付款，提交真实支付结果而不是回滚它。
            current = await MyOrderService.refresh(db, user_id, order_no, wx_code)
            if current.status != 'pending':
                return current
        # 与支付/退款回调保持 txn -> order 锁序。锁后重新读取，避免覆盖并发付款。
        txn = await pay_transaction_dao.get_by_order_no(db, order_no, for_update=True)
        order = await MyOrderService.owned(db, user_id, order_no, for_update=True)
        if order.status != 'pending':
            return MyOrderService.present(order)
        if txn and (txn.user_id != user_id or txn.status not in ('pending', 'closed')):
            raise errors.RequestError(msg='支付状态已变化，请刷新后再操作')
        if txn and order.pay_type in ('jsapi', 'h5'):
            # 可远程关闭的渠道必须成功返回，不能吞掉失败后宣称已取消。
            await get_provider(order.pay_type).close(order_no=order_no)
        now = timezone.now()
        if txn:
            await pay_transaction_dao.update_model(db, txn.id, {'status': 'closed', 'closed_time': now})
        await pay_order_dao.update_model(db, order.id, {'status': 'closed', 'closed_time': now})
        # 非远程关单渠道仍接受迟到到账；user_visible 会恢复这类订单的显示。
        return MyOrderService.present(await MyOrderService.owned(db, user_id, order_no))


my_order_service = MyOrderService()
