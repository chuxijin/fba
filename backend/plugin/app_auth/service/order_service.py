#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy import Select

from backend.common.exception import errors
from backend.database.db import async_db_session
from backend.plugin.app_auth.crud.crud_order import CRUDOrder, order_dao
from backend.plugin.app_auth.model.order import AppOrder
from backend.plugin.app_auth.schema.order import CreateOrderParam, GetOrderDetail, UpdateOrderParam


class OrderService:
    """订单服务"""

    @staticmethod
    async def get(pk: int) -> GetOrderDetail:
        """
        获取订单详情
        
        :param pk: 订单ID
        :return:
        """
        async with async_db_session() as db:
            order = await order_dao.get(db, pk)
            if not order:
                raise errors.NotFoundError(msg='订单不存在')
            return GetOrderDetail.model_validate(order)

    @staticmethod
    def get_select(
        order_no: str | None = None,
        package_id: int | None = None,
        device_id: int | None = None,
        status: int | None = None,
    ) -> Select:
        """
        获取订单查询语句
        
        :param order_no: 订单号
        :param package_id: 套餐ID
        :param device_id: 设备ID
        :param status: 订单状态
        :return:
        """
        return order_dao.get_select(
            order_no=order_no,
            package_id=package_id,
            device_id=device_id,
            status=status,
        )

    @staticmethod
    async def create(obj: CreateOrderParam) -> GetOrderDetail:
        """
        创建订单
        
        :param obj: 订单创建参数
        :return:
        """
        async with AsyncSession() as db:
            # 生成订单号
            import time
            order_no = f"ORD{int(time.time() * 1000)}"
            
            # 获取套餐信息计算总金额
            from backend.plugin.app_auth.crud.crud_package import CRUDPackage
            package = await CRUDPackage.get(db, obj.package_id)
            if not package:
                raise errors.NotFoundError(msg='套餐不存在')
            
            # 创建订单数据
            order_data = {
                'order_no': order_no,
                'package_id': obj.package_id,
                'device_id': obj.device_id,
                'user_id': obj.user_id,
                'username': obj.username,
                'contact_info': obj.contact_info,
                'total_amount': package.current_price,
                'paid_amount': 0,
                'payment_status': 0,  # 未支付
                'order_status': 0,    # 待支付
                'remark': obj.remark,
            }
            
            order = await CRUDOrder.create(db, obj_in=order_data)
            await db.commit()
            await db.refresh(order)
            return GetOrderDetail.model_validate(order)

    @staticmethod
    async def update(pk: int, obj: UpdateOrderParam) -> int:
        """
        更新订单
        
        :param pk: 订单ID
        :param obj: 订单更新参数
        :return:
        """
        async with AsyncSession() as db:
            order = await CRUDOrder.get(db, pk)
            if not order:
                raise errors.NotFoundError(msg='订单不存在')
            
            count = await CRUDOrder.update(db, pk, obj)
            await db.commit()
            return count

    @staticmethod
    async def delete(pk: int) -> int:
        """
        删除订单
        
        :param pk: 订单ID
        :return:
        """
        async with AsyncSession() as db:
            order = await CRUDOrder.get(db, pk)
            if not order:
                raise errors.NotFoundError(msg='订单不存在')
            
            count = await CRUDOrder.delete(db, pk)
            await db.commit()
            return count


order_service = OrderService() 