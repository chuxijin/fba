#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import random
import string

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.payment.crud.crud_pay_transaction import pay_transaction_dao
from backend.app.payment.model.pay_transaction import PayTransaction
from backend.app.payment.schema.pay import CreatePrepayParam, PrepayResult
from backend.app.payment.service.notifier import PaymentNotifier
from backend.common.exception import errors
from backend.common.log import log
from backend.common.payment import get_provider
from backend.common.payment.dispatcher import decrypt_callback
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
        txn = await pay_transaction_dao.create_model(db, txn_data)

        # 调用支付渠道预下单
        provider = get_provider(params.pay_type)
        total_fee = PayService._yuan_to_fen(params.amount)

        result = await provider.prepay(
            order_no=params.order_no,
            total_fee=total_fee,
            description=params.product_name,
            pay_type=params.pay_type,
            openid=params.openid,
            payer_ip=params.payer_ip,
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

        txn = await pay_transaction_dao.get_by_order_no(db, order_no, status='pending')
        if not txn:
            log.warning(f'支付回调未找到待支付记录: order_no={order_no}')
            return

        # 幂等：已支付则跳过
        if txn.status == 'paid':
            log.info(f'支付回调幂等跳过: order_no={order_no}')
            return

        if trade_state != 'SUCCESS':
            log.warning(f'支付未成功: order_no={order_no}, state={trade_state}')
            return

        now = timezone.now()
        await pay_transaction_dao.update_model(
            db,
            txn.id,
            {
                'status': 'paid',
                'trade_no': trade_no,
                'paid_time': now,
                'notify_data': callback_data,
            },
        )

        # 通知业务模块
        if PayService._notifier:
            await PayService._notifier.on_payment_success(
                db=db,
                order_no=order_no,
                trade_no=trade_no or '',
                paid_amount=txn.amount,
            )

        log.info(f'支付回调处理成功: order_no={order_no}, trade_no={trade_no}')

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

        provider = get_provider(txn.pay_type)
        result = await provider.query(order_no=order_no)
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

        provider = get_provider(txn.pay_type)
        result = await provider.refund(
            order_no=order_no,
            refund_no=refund_no,
            total_fee=total_fee,
            refund_fee=refund_fee,
            reason=reason,
        )

        now = timezone.now()
        await pay_transaction_dao.update_model(
            db,
            txn.id,
            {
                'status': 'refund_pending',
                'refund_no': refund_no,
                'refund_amount': actual_refund,
            },
        )

        log.info(f'退款提交成功: order_no={order_no}, refund_no={refund_no}')
        return {'refund_no': refund_no, 'status': result.get('status', 'PROCESSING')}

    @staticmethod
    async def close_payment(*, db: AsyncSession, order_no: str) -> None:
        """
        关闭支付（供订单取消时调用）

        :param db: 数据库会话
        :param order_no: 业务订单号
        :return:
        """
        txn = await pay_transaction_dao.get_by_order_no(db, order_no, status='pending')
        if not txn:
            return

        try:
            provider = get_provider(txn.pay_type)
            await provider.close(order_no=order_no)
        except Exception as e:
            log.warning(f'关闭预付单失败: order_no={order_no}, error={e}')

        now = timezone.now()
        await pay_transaction_dao.update_model(
            db,
            txn.id,
            {'status': 'closed', 'closed_time': now},
        )

        # 通知业务模块
        if PayService._notifier:
            await PayService._notifier.on_payment_closed(db=db, order_no=order_no)

        log.info(f'支付关闭成功: order_no={order_no}')


pay_service: PayService = PayService()

# 注册商城支付通知器
from backend.app.mall.service.payment_notifier import mall_payment_notifier

pay_service.register_notifier(mall_payment_notifier)
