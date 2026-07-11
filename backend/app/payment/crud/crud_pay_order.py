#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.payment.model.pay_order import PayOrder


class CRUDPayOrder(CRUDPlus[PayOrder]):
    """支付业务订单数据库操作类"""

    async def create_from_dict(self, db: AsyncSession, data: dict[str, object]) -> PayOrder:
        """
        通过字典创建支付业务订单

        :param db: 数据库会话
        :param data: 订单数据
        :return:
        """
        order = PayOrder(**data)
        db.add(order)
        await db.flush()
        return order

    async def get(self, db: AsyncSession, pk: int) -> PayOrder | None:
        """
        获取支付业务订单详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_order_no(self, db: AsyncSession, order_no: str) -> PayOrder | None:
        """
        通过业务订单号查询

        :param db: 数据库会话
        :param order_no: 业务订单号
        :return:
        """
        return await self.select_model_by_column(db, order_no=order_no)

    async def get_by_user(self, db: AsyncSession, user_id: int, status: str | None = None) -> list[PayOrder]:
        """
        获取用户支付业务订单列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param status: 状态过滤
        :return:
        """
        stmt = select(PayOrder).where(PayOrder.user_id == user_id)
        if status:
            stmt = stmt.where(PayOrder.status == status)
        stmt = stmt.order_by(PayOrder.created_time.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_timeout_pending_orders(
        self,
        db: AsyncSession,
        *,
        created_before: datetime,
        limit: int = 100,
    ) -> list[PayOrder]:
        """
        获取超时未支付订单

        :param db: 数据库会话
        :param created_before: 创建时间上限
        :param limit: 批量数量
        :return:
        """
        stmt = (
            select(PayOrder)
            .where(PayOrder.status == 'pending', PayOrder.created_time < created_before)
            .order_by(PayOrder.created_time.asc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())


pay_order_dao = CRUDPayOrder(PayOrder)
