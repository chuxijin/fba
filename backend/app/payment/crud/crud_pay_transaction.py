#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.payment.model.pay_transaction import PayTransaction


class CRUDPayTransaction(CRUDPlus[PayTransaction]):
    """支付记录数据库操作类"""

    async def create_from_dict(self, db: AsyncSession, data: dict[str, object]) -> PayTransaction:
        """
        通过字典创建支付记录

        :param db: 数据库会话
        :param data: 支付记录数据
        :return:
        """
        transaction = PayTransaction(**data)
        db.add(transaction)
        await db.flush()
        return transaction

    async def get(self, db: AsyncSession, pk: int) -> PayTransaction | None:
        """
        获取支付记录详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_transaction_no(self, db: AsyncSession, transaction_no: str) -> PayTransaction | None:
        """
        通过内部交易号查询

        :param db: 数据库会话
        :param transaction_no: 内部交易号
        :return:
        """
        stmt = select(PayTransaction).where(PayTransaction.transaction_no == transaction_no)
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_by_order_no(
        self, db: AsyncSession, order_no: str, status: str | None = None
    ) -> PayTransaction | None:
        """
        通过业务订单号查询（取最新一条）

        :param db: 数据库会话
        :param order_no: 业务订单号
        :param status: 状态过滤
        :return:
        """
        stmt = select(PayTransaction).where(PayTransaction.order_no == order_no)
        if status:
            stmt = stmt.where(PayTransaction.status == status)
        stmt = stmt.order_by(PayTransaction.created_time.desc())
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_by_user(self, db: AsyncSession, user_id: int, status: str | None = None) -> list[PayTransaction]:
        """
        获取用户的支付记录列表

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param status: 状态过滤
        :return:
        """
        filters = {'user_id': user_id}
        if status:
            filters['status'] = status
        return await self.select_models(db, order_by='created_time', order_direction='desc', **filters)


pay_transaction_dao = CRUDPayTransaction(PayTransaction)
