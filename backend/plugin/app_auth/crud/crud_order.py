#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.app_auth.model import AppOrder
from backend.plugin.app_auth.schema.order import CreateOrderParam, UpdateOrderParam


class CRUDOrder(CRUDPlus[AppOrder]):
    """订单数据库操作类"""

    async def get(self, db: AsyncSession, order_id: int) -> AppOrder | None:
        """
        获取订单详情

        :param db: 数据库会话
        :param order_id: 订单 ID
        :return:
        """
        return await self.select_model(db, order_id)

    async def get_by_order_no(self, db: AsyncSession, order_no: str) -> AppOrder | None:
        """
        通过订单号获取订单

        :param db: 数据库会话
        :param order_no: 订单号
        :return:
        """
        return await self.select_model_by_column(db, order_no=order_no)

    async def create(self, db: AsyncSession, obj_in: CreateOrderParam, total_amount: Decimal) -> AppOrder:
        """
        创建订单

        :param db: 数据库会话
        :param obj_in: 创建参数
        :param total_amount: 订单总金额
        :return:
        """
        # 生成订单号
        order_no = f"ORD{uuid.uuid4().hex[:16].upper()}"
        
        order_data = obj_in.model_dump()
        order_data.update({
            'order_no': order_no,
            'total_amount': total_amount,
            'paid_amount': Decimal('0.00')
        })
        
        return await self.create_model(db, order_data)

    async def update(self, db: AsyncSession, order_id: int, obj_in: UpdateOrderParam) -> int:
        """
        更新订单

        :param db: 数据库会话
        :param order_id: 订单 ID
        :param obj_in: 更新参数
        :return:
        """
        return await self.update_model(db, order_id, obj_in)

    async def delete(self, db: AsyncSession, order_id: int) -> int:
        """删除订单"""
        return await self.delete_model(db, order_id)

    async def get_list(self, db: AsyncSession, order_no: str = None, package_id: int = None, 
                      device_id: int = None, status: int = None) -> list[AppOrder]:
        """获取订单列表"""
        stmt = select(self.model)
        if order_no:
            stmt = stmt.where(self.model.order_no.like(f'%{order_no}%'))
        if package_id:
            stmt = stmt.where(self.model.package_id == package_id)
        if device_id:
            stmt = stmt.where(self.model.device_id == device_id)
        if status is not None:
            stmt = stmt.where(self.model.status == status)
        stmt = stmt.order_by(self.model.created_time.desc())
        return await self.select_models(db, stmt)

    def get_select(self, order_no: str = None, package_id: int = None, 
                  device_id: int = None, status: int = None):
        """获取订单查询语句"""
        stmt = select(self.model)
        if order_no:
            stmt = stmt.where(self.model.order_no.like(f'%{order_no}%'))
        if package_id:
            stmt = stmt.where(self.model.package_id == package_id)
        if device_id:
            stmt = stmt.where(self.model.device_id == device_id)
        if status is not None:
            stmt = stmt.where(self.model.status == status)
        stmt = stmt.order_by(self.model.created_time.desc())
        return stmt


order_dao: CRUDOrder = CRUDOrder(AppOrder)