#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import random
import string

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.mall.crud.crud_order import order_dao
from backend.app.mall.crud.crud_product import product_sku_dao
from backend.common.exception import errors
from backend.common.log import log
from backend.common.payment import get_provider
from backend.utils.timezone import timezone


class PaymentService:
    """支付服务类"""

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
    async def prepay(
        *, db: AsyncSession, order_id: int, user_id: int, pay_type: str, openid: str | None = None,
        payer_ip: str | None = None
    ) -> dict:
        """
        预下单

        :param db: 数据库会话
        :param order_id: 订单 ID
        :param user_id: 用户 ID
        :param pay_type: 支付方式
        :param openid: 用户 openid
        :param payer_ip: 用户 IP
        :return:
        """
        order = await order_dao.get(db, order_id)
        if not order:
            raise errors.NotFoundError(msg='订单不存在')

        if order.user_id != user_id:
            raise errors.ForbiddenError(msg='无权操作该订单')

        if order.status != 'pending':
            raise errors.ForbiddenError(msg='订单状态不允许支付')

        # 更新支付方式
        await order_dao.update_model(db, order_id, {'pay_type': pay_type})

        # 调用支付渠道预下单
        provider = get_provider(pay_type)
        total_fee = PaymentService._yuan_to_fen(order.total_amount)

        result = await provider.prepay(
            order_no=order.order_no,
            total_fee=total_fee,
            description=order.product_name,
            pay_type=pay_type,
            openid=openid,
            payer_ip=payer_ip,
        )

        log.info(f'预下单成功: order_id={order_id}, pay_type={pay_type}')
        return result

    @staticmethod
    async def handle_pay_callback(*, db: AsyncSession, headers: dict, body: bytes) -> None:
        """
        处理支付回调通知

        :param db: 数据库会话
        :param headers: 请求头
        :param body: 请求体
        :return:
        """
        # 当前只有微信，直接用微信 provider 解密
        from backend.common.payment.providers.wechat import wechat_pay_provider

        callback_data = wechat_pay_provider.decrypt_callback(headers=headers, body=body)

        order_no = callback_data.get('out_trade_no')
        trade_no = callback_data.get('transaction_id')
        trade_state = callback_data.get('trade_state')

        if not order_no:
            log.error(f'支付回调缺少订单号: {callback_data}')
            return

        order = await order_dao.get_by_order_no(db, order_no)
        if not order:
            log.error(f'支付回调订单不存在: order_no={order_no}')
            return

        # 幂等：已支付则跳过
        if order.status == 'paid':
            log.info(f'支付回调幂等跳过: order_no={order_no}')
            return

        if trade_state != 'SUCCESS':
            log.warning(f'支付未成功: order_no={order_no}, state={trade_state}')
            return

        now = timezone.now()
        await order_dao.update_model(
            db,
            order.id,
            {
                'status': 'paid',
                'paid_amount': order.total_amount,
                'paid_time': now,
                'trade_no': trade_no,
            },
        )

        # 扣减库存
        await product_sku_dao.update_model(db, order.sku_id, {})
        # TODO: 扣减库存的具体逻辑（stock -= quantity, sales_count += quantity）

        log.info(f'支付回调处理成功: order_no={order_no}, trade_no={trade_no}')

    @staticmethod
    async def query_payment(*, db: AsyncSession, order_id: int, user_id: int) -> dict:
        """
        查询支付状态

        :param db: 数据库会话
        :param order_id: 订单 ID
        :param user_id: 用户 ID
        :return:
        """
        order = await order_dao.get(db, order_id)
        if not order:
            raise errors.NotFoundError(msg='订单不存在')

        if order.user_id != user_id:
            raise errors.ForbiddenError(msg='无权操作该订单')

        if not order.pay_type:
            raise errors.ForbiddenError(msg='该订单尚未发起支付')

        provider = get_provider(order.pay_type)
        return await provider.query(order_no=order.order_no)

    @staticmethod
    async def refund(
        *, db: AsyncSession, order_id: int, user_id: int, refund_amount: Decimal | None = None,
        reason: str | None = None
    ) -> dict:
        """
        申请退款

        :param db: 数据库会话
        :param order_id: 订单 ID
        :param user_id: 用户 ID
        :param refund_amount: 退款金额
        :param reason: 退款原因
        :return:
        """
        order = await order_dao.get(db, order_id)
        if not order:
            raise errors.NotFoundError(msg='订单不存在')

        if order.user_id != user_id:
            raise errors.ForbiddenError(msg='无权操作该订单')

        if order.status != 'paid':
            raise errors.ForbiddenError(msg='订单状态不允许退款')

        if not order.pay_type:
            raise errors.ForbiddenError(msg='该订单无支付记录')

        actual_refund = refund_amount or order.paid_amount
        total_fee = PaymentService._yuan_to_fen(order.total_amount)
        refund_fee = PaymentService._yuan_to_fen(actual_refund)
        refund_no = PaymentService._generate_refund_no()

        provider = get_provider(order.pay_type)
        result = await provider.refund(
            order_no=order.order_no,
            refund_no=refund_no,
            total_fee=total_fee,
            refund_fee=refund_fee,
            reason=reason,
        )

        now = timezone.now()
        await order_dao.update_model(
            db,
            order.id,
            {'status': 'refunded', 'refunded_time': now},
        )

        log.info(f'退款提交成功: order_no={order.order_no}, refund_no={refund_no}')
        return {'refund_id': refund_no, 'status': result.get('status', 'PROCESSING')}

    @staticmethod
    async def handle_refund_callback(*, db: AsyncSession, headers: dict, body: bytes) -> None:
        """
        处理退款回调通知

        :param db: 数据库会话
        :param headers: 请求头
        :param body: 请求体
        :return:
        """
        from backend.common.payment.providers.wechat import wechat_pay_provider

        callback_data = wechat_pay_provider.decrypt_callback(headers=headers, body=body)
        order_no = callback_data.get('out_trade_no')
        refund_status = callback_data.get('refund_status')

        if not order_no:
            log.error(f'退款回调缺少订单号: {callback_data}')
            return

        order = await order_dao.get_by_order_no(db, order_no)
        if not order:
            log.error(f'退款回调订单不存在: order_no={order_no}')
            return

        if refund_status == 'SUCCESS':
            now = timezone.now()
            await order_dao.update_model(
                db,
                order.id,
                {'status': 'refunded', 'refunded_time': now},
            )
            log.info(f'退款回调成功: order_no={order_no}')
        else:
            log.warning(f'退款回调状态异常: order_no={order_no}, status={refund_status}')


payment_service: PaymentService = PaymentService()
