#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import random
import string

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.payment.crud.crud_pay_order import pay_order_dao
from backend.app.payment.crud.crud_pay_transaction import pay_transaction_dao
from backend.app.payment.schema.pay import CreatePrepayParam, PrepayResult
from backend.app.payment.service.notifier import PaymentNotifier
from backend.app.payment.service.subscription_notifier import subscription_payment_notifier
from backend.common.exception import errors
from backend.common.log import log
from backend.common.payment import get_provider
from backend.common.payment.dispatcher import decrypt_callback
from backend.core.conf import settings
from backend.utils.timezone import timezone


class PayService:
    """支付服务类"""

    _notifier: PaymentNotifier | None = None

    @classmethod
    def register_notifier(cls, notifier: PaymentNotifier) -> None:
        """注册业务通知器（由业务模块在启动时调用）"""
        cls._notifier = notifier

    @staticmethod
    def _generate_transaction_no() -> str:
        """生成内部交易号"""
        now = timezone.now()
        timestamp = now.strftime('%Y%m%d%H%M%S')
        random_suffix = ''.join(random.choices(string.digits, k=6))
        return f'PAY{timestamp}{random_suffix}'

    @staticmethod
    def _generate_refund_no() -> str:
        """生成退款单号"""
        now = timezone.now()
        timestamp = now.strftime('%Y%m%d%H%M%S')
        random_suffix = ''.join(random.choices(string.digits, k=6))
        return f'REF{timestamp}{random_suffix}'

    @staticmethod
    def _yuan_to_fen(amount: Decimal) -> int:
        """
        元转分

        :param amount: 金额（元）
        :return:
        """
        return int(amount * 100)

    @staticmethod
    def _resolve_paid_time(paid_time: Any = None) -> datetime:
        """
        解析支付完成时间

        :param paid_time: 渠道返回的支付时间
        :return:
        """
        if isinstance(paid_time, int | float) and paid_time > 0:
            return timezone.from_datetime(timezone.to_utc(int(paid_time)))
        return timezone.now()

    @staticmethod
    async def _mark_payment_success(
        *,
        db: AsyncSession,
        txn_id: int,
        order_no: str,
        trade_no: str,
        paid_time: datetime,
        notify_data: dict[str, Any],
    ) -> None:
        """
        标记支付成功并通知业务发放

        :param db: 数据库会话
        :param txn_id: 支付记录 ID
        :param order_no: 业务订单号
        :param trade_no: 第三方交易号
        :param paid_time: 支付时间
        :param notify_data: 渠道通知或查询数据
        :return:
        """
        txn = await pay_transaction_dao.get(db, txn_id)
        if not txn:
            log.warning(f'支付成功处理未找到支付记录: order_no={order_no}, txn_id={txn_id}')
            return

        if txn.status != 'paid':
            await pay_transaction_dao.update_model(
                db,
                txn.id,
                {
                    'status': 'paid',
                    'trade_no': trade_no,
                    'paid_time': paid_time,
                    'notify_data': notify_data,
                },
            )

        pay_order = await pay_order_dao.get_by_order_no(db, order_no)
        if pay_order and pay_order.status != 'paid':
            await pay_order_dao.update_model(
                db,
                pay_order.id,
                {
                    'status': 'paid',
                    'trade_no': trade_no,
                    'paid_time': paid_time,
                },
            )

        if PayService._notifier:
            await PayService._notifier.on_payment_success(
                db=db,
                order_no=order_no,
                trade_no=trade_no,
                paid_amount=txn.amount,
            )

    @staticmethod
    async def create_prepay(*, db: AsyncSession, params: CreatePrepayParam) -> PrepayResult:
        """
        创建预支付

        :param db: 数据库会话
        :param params: 预支付参数
        :return:
        """
        # 检查是否已有该 order_no 的 pending/paid 记录（幂等）
        existing = await pay_transaction_dao.get_by_order_no(db, params.order_no)
        if existing and existing.status in ('pending', 'paid'):
            if existing.status == 'paid':
                raise errors.ForbiddenError(msg='该订单已支付')
            # pending 状态：关闭旧记录，重新下单
            existing.status = 'closed'
            existing.closed_time = timezone.now()
            await db.flush()

        transaction_no = PayService._generate_transaction_no()

        # 创建支付记录
        txn_data = {
            'transaction_no': transaction_no,
            'order_no': params.order_no,
            'biz_type': params.biz_type,
            'user_id': params.user_id,
            'pay_type': params.pay_type,
            'amount': params.amount,
            'status': 'pending',
            'product_name': params.product_name,
            'created_by': params.user_id,
        }
        await pay_transaction_dao.create_from_dict(db, txn_data)

        # 调用支付渠道预下单
        provider = get_provider(params.pay_type)
        total_fee = PayService._yuan_to_fen(params.amount)

        result = await provider.prepay(
            order_no=params.order_no,
            total_fee=total_fee,
            description=params.product_name,
            pay_type=params.pay_type,
            openid=params.openid,
            session_key=params.session_key,
            product_id=params.product_id,
            payer_ip=params.payer_ip,
            env=params.env,
        )

        log.info(f'预下单成功: order_no={params.order_no}, transaction_no={transaction_no}, pay_type={params.pay_type}')
        return PrepayResult(pay_params=result, transaction_no=transaction_no)

    @staticmethod
    async def handle_pay_callback(*, db: AsyncSession, headers: dict, body: bytes) -> None:
        """
        处理支付回调通知

        :param db: 数据库会话
        :param headers: 请求头
        :param body: 请求体
        :return:
        """
        raw_data, provider = decrypt_callback(headers=headers, body=body)
        callback_data = provider.normalize_callback_data(raw_data, event='payment')

        order_no = callback_data.get('order_no')
        trade_no = callback_data.get('trade_no')
        trade_state = callback_data.get('trade_state')

        if not order_no:
            log.error(f'支付回调缺少订单号: {callback_data}')
            return

        txn = await pay_transaction_dao.get_by_order_no(db, order_no)
        if not txn:
            log.warning(f'支付回调未找到待支付记录: order_no={order_no}')
            return

        # 幂等：已支付则跳过
        if txn.status == 'paid':
            pay_order = await pay_order_dao.get_by_order_no(db, order_no)
            if PayService._notifier and pay_order and pay_order.fulfill_status != 'fulfilled':
                await PayService._notifier.on_payment_success(
                    db=db,
                    order_no=order_no,
                    trade_no=trade_no or txn.trade_no or '',
                    paid_amount=txn.amount,
                )
            log.info(f'支付回调幂等跳过: order_no={order_no}')
            return

        if trade_state != 'SUCCESS':
            log.warning(f'支付未成功: order_no={order_no}, state={trade_state}')
            return

        paid_time = PayService._resolve_paid_time(callback_data.get('paid_time'))
        await PayService._mark_payment_success(
            db=db,
            txn_id=txn.id,
            order_no=order_no,
            trade_no=trade_no or '',
            paid_time=paid_time,
            notify_data=callback_data,
        )

        log.info(f'支付回调处理成功: order_no={order_no}, trade_no={trade_no}')

    @staticmethod
    async def sync_payment_status(
        *, db: AsyncSession, order_no: str, user_id: int, openid: str | None = None
    ) -> dict[str, Any]:
        """
        主动同步支付状态并发放权益

        :param db: 数据库会话
        :param order_no: 业务订单号
        :param user_id: 用户 ID
        :param openid: 微信 openid
        :return:
        """
        txn = await pay_transaction_dao.get_by_order_no(db, order_no)
        if not txn:
            raise errors.NotFoundError(msg='支付记录不存在')
        if txn.user_id != user_id:
            raise errors.ForbiddenError(msg='无权查询该支付记录')

        pay_order = await pay_order_dao.get_by_order_no(db, order_no)
        if not pay_order:
            raise errors.NotFoundError(msg='支付订单不存在')
        if pay_order.user_id != user_id:
            raise errors.ForbiddenError(msg='无权查询该支付订单')

        if txn.status == 'paid':
            if PayService._notifier and pay_order.fulfill_status != 'fulfilled':
                await PayService._notifier.on_payment_success(
                    db=db,
                    order_no=order_no,
                    trade_no=txn.trade_no or '',
                    paid_amount=txn.amount,
                )
            pay_order = await pay_order_dao.get_by_order_no(db, order_no)
            return {
                'order_no': order_no,
                'status': pay_order.status if pay_order else 'paid',
                'fulfill_status': pay_order.fulfill_status if pay_order else 'fulfilled',
                'paid': True,
                'fulfilled': bool(pay_order and pay_order.fulfill_status == 'fulfilled'),
            }

        env = int((pay_order.extra_data or {}).get('env') or 0)
        if txn.pay_type == 'virtual' and not openid:
            raise errors.RequestError(msg='确认虚拟支付状态需要微信登录 code')

        provider = get_provider(txn.pay_type)
        query_result = await provider.query(order_no=order_no, env=env, openid=openid)
        query_data = provider.normalize_query_data(query_result, order_no=order_no)
        trade_state = query_data.get('trade_state')

        if trade_state == 'SUCCESS':
            paid_time = PayService._resolve_paid_time(query_data.get('paid_time'))
            await PayService._mark_payment_success(
                db=db,
                txn_id=txn.id,
                order_no=order_no,
                trade_no=str(query_data.get('trade_no') or ''),
                paid_time=paid_time,
                notify_data=query_data,
            )
        else:
            log.info(f'主动同步支付状态未支付: order_no={order_no}, state={trade_state}')

        pay_order = await pay_order_dao.get_by_order_no(db, order_no)
        return {
            'order_no': order_no,
            'status': pay_order.status if pay_order else 'pending',
            'fulfill_status': pay_order.fulfill_status if pay_order else 'pending',
            'paid': bool(pay_order and pay_order.status == 'paid'),
            'fulfilled': bool(pay_order and pay_order.fulfill_status == 'fulfilled'),
        }

    @staticmethod
    async def handle_refund_callback(*, db: AsyncSession, headers: dict, body: bytes) -> None:
        """
        处理退款回调通知

        :param db: 数据库会话
        :param headers: 请求头
        :param body: 请求体
        :return:
        """
        raw_data, provider = decrypt_callback(headers=headers, body=body)
        callback_data = provider.normalize_callback_data(raw_data, event='refund')

        order_no = callback_data.get('order_no')
        refund_status = callback_data.get('refund_status')

        if not order_no:
            log.error(f'退款回调缺少订单号: {callback_data}')
            return

        txn = await pay_transaction_dao.get_by_order_no(db, order_no)
        if not txn:
            log.error(f'退款回调未找到支付记录: order_no={order_no}')
            return

        if refund_status == 'SUCCESS':
            now = timezone.now()
            await pay_transaction_dao.update_model(
                db,
                txn.id,
                {
                    'status': 'refunded',
                    'refunded_time': now,
                    'notify_data': callback_data,
                },
            )

            pay_order = await pay_order_dao.get_by_order_no(db, order_no)
            if pay_order:
                await pay_order_dao.update_model(
                    db,
                    pay_order.id,
                    {'status': 'refunded', 'refunded_time': now},
                )

            # 通知业务模块
            if PayService._notifier:
                await PayService._notifier.on_refund_success(db=db, order_no=order_no)

            log.info(f'退款回调成功: order_no={order_no}')
        else:
            log.warning(f'退款回调状态异常: order_no={order_no}, status={refund_status}')

    @staticmethod
    async def query_payment(*, db: AsyncSession, order_no: str, user_id: int) -> dict:
        """
        查询支付状态

        :param db: 数据库会话
        :param order_no: 业务订单号
        :param user_id: 用户 ID
        :return:
        """
        txn = await pay_transaction_dao.get_by_order_no(db, order_no)
        if not txn:
            raise errors.NotFoundError(msg='支付记录不存在')

        if txn.user_id != user_id:
            raise errors.ForbiddenError(msg='无权查询该支付记录')

        if not txn.pay_type:
            raise errors.ForbiddenError(msg='该记录尚未发起支付')

        pay_order = await pay_order_dao.get_by_order_no(db, order_no)
        env = int((pay_order.extra_data or {}).get('env') or 0) if pay_order else 0
        openid = str((pay_order.extra_data or {}).get('openid') or '') if pay_order else ''

        provider = get_provider(txn.pay_type)
        result = await provider.query(order_no=order_no, env=env, openid=openid or None)
        return result

    @staticmethod
    async def refund(
        *,
        db: AsyncSession,
        order_no: str,
        user_id: int,
        refund_amount: Decimal | None = None,
        reason: str | None = None,
    ) -> dict:
        """
        申请退款

        :param db: 数据库会话
        :param order_no: 业务订单号
        :param user_id: 用户 ID
        :param refund_amount: 退款金额
        :param reason: 退款原因
        :return:
        """
        txn = await pay_transaction_dao.get_by_order_no(db, order_no, status='paid')
        if not txn:
            raise errors.NotFoundError(msg='未找到已支付的记录')

        if txn.user_id != user_id:
            raise errors.ForbiddenError(msg='无权操作该支付记录')

        actual_refund = refund_amount or txn.amount
        total_fee = PayService._yuan_to_fen(txn.amount)
        refund_fee = PayService._yuan_to_fen(actual_refund)
        refund_no = PayService._generate_refund_no()

        pay_order = await pay_order_dao.get_by_order_no(db, order_no)
        env = int((pay_order.extra_data or {}).get('env') or 0) if pay_order else 0

        provider = get_provider(txn.pay_type)
        result = await provider.refund(
            order_no=order_no,
            refund_no=refund_no,
            total_fee=total_fee,
            refund_fee=refund_fee,
            reason=reason,
            env=env,
        )

        await pay_transaction_dao.update_model(
            db,
            txn.id,
            {
                'status': 'refund_pending',
                'refund_no': refund_no,
                'refund_amount': actual_refund,
            },
        )
        if pay_order:
            await pay_order_dao.update_model(
                db,
                pay_order.id,
                {'status': 'refund_pending'},
            )

        log.info(f'退款提交成功: order_no={order_no}, refund_no={refund_no}')
        return {'refund_no': refund_no, 'status': result.get('status', 'PROCESSING')}

    @staticmethod
    async def close_payment(*, db: AsyncSession, order_no: str) -> bool:
        """
        关闭支付（供订单取消时调用）

        :param db: 数据库会话
        :param order_no: 业务订单号
        :return:
        """
        pay_order = await pay_order_dao.get_by_order_no(db, order_no)
        txn = await pay_transaction_dao.get_by_order_no(db, order_no, status='pending')
        if not txn and not pay_order:
            return False

        should_close_order = bool(pay_order and pay_order.status == 'pending')
        if not txn and not should_close_order:
            return False

        now = timezone.now()
        if txn:
            try:
                env = int((pay_order.extra_data or {}).get('env') or 0) if pay_order else 0
                provider = get_provider(txn.pay_type)
                await provider.close(order_no=order_no, env=env)
            except Exception as e:
                log.warning(f'关闭预付单失败: order_no={order_no}, error={e}')

            await pay_transaction_dao.update_model(
                db,
                txn.id,
                {'status': 'closed', 'closed_time': now},
            )

        if should_close_order and pay_order:
            await pay_order_dao.update_model(db, pay_order.id, {'status': 'closed', 'closed_time': now})

        # 通知业务模块
        if PayService._notifier and should_close_order:
            await PayService._notifier.on_payment_closed(db=db, order_no=order_no)

        log.info(f'支付关闭成功: order_no={order_no}')
        return True

    @staticmethod
    async def close_timeout_pending_orders(
        *,
        db: AsyncSession,
        timeout_minutes: int | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """
        批量关闭超时未支付订单

        :param db: 数据库会话
        :param timeout_minutes: 超时分钟数
        :param limit: 单次处理上限
        :return:
        """
        effective_timeout = max(int(timeout_minutes or settings.PAYMENT_PENDING_ORDER_TIMEOUT_MINUTES), 1)
        batch_limit = max(int(limit), 1)
        threshold = timezone.now() - timedelta(minutes=effective_timeout)
        orders = await pay_order_dao.get_timeout_pending_orders(
            db,
            created_before=threshold,
            limit=batch_limit,
        )
        order_nos = [order.order_no for order in orders]
        summary: dict[str, Any] = {
            'timeout_minutes': effective_timeout,
            'threshold': threshold.isoformat(),
            'scanned_count': len(order_nos),
            'closed_count': 0,
            'skipped_count': 0,
            'failed_count': 0,
            'closed_order_nos': [],
            'skipped_order_nos': [],
            'failed_order_nos': [],
        }

        for order_no in order_nos:
            try:
                closed = await PayService.close_payment(db=db, order_no=order_no)
                if not closed:
                    summary['skipped_order_nos'].append(order_no)
                    continue

                await db.commit()
                summary['closed_order_nos'].append(order_no)
            except Exception as exc:
                await db.rollback()
                summary['failed_order_nos'].append(order_no)
                log.error(f'关闭超时支付订单失败: order_no={order_no}, error={exc}')

        summary['closed_count'] = len(summary['closed_order_nos'])
        summary['skipped_count'] = len(summary['skipped_order_nos'])
        summary['failed_count'] = len(summary['failed_order_nos'])
        return summary


pay_service: PayService = PayService()

# 注册订阅支付通知器
pay_service.register_notifier(subscription_payment_notifier)
