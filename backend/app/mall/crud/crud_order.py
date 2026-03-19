#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.mall.model.order import Order


class CRUDOrder(CRUDPlus[Order]):
    """订单数据库操作类"""

    async def get(self, db: AsyncSession, order_id: int) -> Order | None:
        """
        获取订单详情

        :param db: 数据库会话
        :param order_id: 订单 ID
        :return:
        """
        return await self.select_model(db, order_id)

    async def get_by_order_no(self, db: AsyncSession, order_no: str) -> Order | None:
        """
        通过订单号获取订单

        :param db: 数据库会话
        :param order_no: 订单号
        :return:
        """
        stmt = select(Order).where(Order.order_no == order_no)
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_by_user(self, db: AsyncSession, user_id: int, status: str | None = None) -> list[Order]:
        """
        获取用户的订单列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param status: 订单状态
        :return:
        """
        filters = {'user_id': user_id}
        if status:
            filters['status'] = status
        return await self.select_models(db, **filters)

    async def get_by_team(self, db: AsyncSession, team_id: int) -> list[Order]:
        """
        获取拼团团队的订单列表

        :param db: 数据库会话
        :param team_id: 团队 ID
        :return:
        """
        filters = {'team_id': team_id}
        return await self.select_models(db, **filters)


order_dao = CRUDOrder(Order)
