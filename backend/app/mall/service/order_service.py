#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.mall.crud.crud_group_buy_team import group_buy_team_dao
from backend.app.mall.crud.crud_order import order_dao
from backend.app.mall.crud.crud_product import product_dao, product_sku_dao
from backend.app.mall.model.order import Order
from backend.app.mall.schema.order import CreateOrderParam, CreateOrderRecord
from backend.common.exception import errors
from backend.utils.timezone import timezone

log = logging.getLogger(__name__)


class OrderService:
    """订单服务类"""

    @staticmethod
    def _generate_order_no() -> str:
        """生成订单号"""
        now = timezone.now()
        timestamp = now.strftime('%Y%m%d%H%M%S')
        import random

        random_suffix = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        return f'ORD{timestamp}{random_suffix}'

    @staticmethod
    async def create_order(*, db: AsyncSession, obj: CreateOrderParam, user_id: int) -> Order:
        """
        创建订单

        :param db: 数据库会话
        :param obj: 创建参数
        :param user_id: 用户 ID
        :return:
        """
        product = await product_dao.get(db, obj.product_id)
        if not product:
            raise errors.NotFoundError(msg='商品不存在')

        sku = await product_sku_dao.get(db, obj.sku_id)
        if not sku or sku.product_id != obj.product_id:
            raise errors.NotFoundError(msg='SKU 不存在或不属于该商品')

        if not sku.is_active:
            raise errors.ForbiddenError(msg='SKU 已下架')

        if sku.stock < obj.quantity:
            raise errors.ForbiddenError(msg='库存不足')

        unit_price = sku.price
        if obj.order_type == 'group_buy':
            if not obj.team_id:
                raise errors.ForbiddenError(msg='拼团订单必须指定团队 ID')
            team = await group_buy_team_dao.get(db, obj.team_id)
            if not team:
                raise errors.NotFoundError(msg='拼团团队不存在')
            unit_price = team.team_price

        total_amount = unit_price * obj.quantity

        order_no = OrderService._generate_order_no()
        order_data = CreateOrderRecord(
            order_no=order_no,
            user_id=user_id,
            order_type=obj.order_type,
            product_id=obj.product_id,
            sku_id=obj.sku_id,
            product_name=product.name,
            sku_name=sku.sku_name,
            quantity=obj.quantity,
            unit_price=unit_price,
            total_amount=total_amount,
            status='pending',
            team_id=obj.team_id,
            activity_id=obj.activity_id,
            remark=obj.remark,
        )

        order = await order_dao.create_model(db, order_data)
        log.info(f'用户 {user_id} 创建订单，订单号: {order_no}')
        return order

    @staticmethod
    async def get_order(*, db: AsyncSession, order_id: int) -> Order:
        """
        获取订单详情

        :param db: 数据库会话
        :param order_id: 订单 ID
        :return:
        """
        order = await order_dao.get(db, order_id)
        if not order:
            raise errors.NotFoundError(msg='订单不存在')
        return order

    @staticmethod
    async def get_order_by_no(*, db: AsyncSession, order_no: str) -> Order:
        """
        通过订单号获取订单

        :param db: 数据库会话
        :param order_no: 订单号
        :return:
        """
        order = await order_dao.get_by_order_no(db, order_no)
        if not order:
            raise errors.NotFoundError(msg='订单不存在')
        return order

    @staticmethod
    async def get_user_orders(*, db: AsyncSession, user_id: int, status: str | None = None) -> list[Order]:
        """
        获取用户的订单列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param status: 订单状态
        :return:
        """
        return await order_dao.get_by_user(db, user_id, status)

    @staticmethod
    async def pay_order(*, db: AsyncSession, order_id: int, user_id: int) -> Order:
        """
        支付订单（模拟支付）

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

        if order.status != 'pending':
            raise errors.ForbiddenError(msg='订单状态不允许支付')

        now = timezone.now()
        await order_dao.update_model(
            db,
            order_id,
            {
                'status': 'paid',
                'paid_amount': order.total_amount,
                'paid_time': now,
            },
        )

        log.info(f'用户 {user_id} 支付订单，订单号: {order.order_no}')
        return await order_dao.get(db, order_id)

    @staticmethod
    async def cancel_order(*, db: AsyncSession, order_id: int, user_id: int) -> int:
        """
        取消订单

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

        if order.status not in ['pending']:
            raise errors.ForbiddenError(msg='订单状态不允许取消')

        # 如果已发起过预下单，关闭支付记录
        if order.pay_type:
            from backend.app.payment.service.pay_service import pay_service

            await pay_service.close_payment(db=db, order_no=order.order_no)

        now = timezone.now()
        count = await order_dao.update_model(
            db,
            order_id,
            {
                'status': 'cancelled',
                'cancelled_time': now,
            },
        )

        log.info(f'用户 {user_id} 取消订单，订单号: {order.order_no}')
        return count


order_service = OrderService()
