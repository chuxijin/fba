#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.mall.schema.order import CreateOrderParam, GetOrderDetail, GetOrderListItem
from backend.app.mall.service.order_service import order_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(prefix='/order', tags=['订单管理'])


@router.post('', summary='创建订单', dependencies=[DependsJwtAuth])
async def mall_create_order(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateOrderParam,
) -> ResponseSchemaModel[GetOrderDetail]:
    """创建订单"""
    order = await order_service.create_order(db=db, obj=obj, user_id=request.user.id)
    return response_base.success(data=GetOrderDetail.model_validate(order))


@router.get('/my', summary='获取我的订单列表', dependencies=[DependsJwtAuth])
async def mall_get_my_orders(
    request: Request,
    db: CurrentSession,
    status: Annotated[str | None, Query(description='订单状态')] = None,
) -> ResponseSchemaModel[list[GetOrderListItem]]:
    """获取我的订单列表"""
    orders = await order_service.get_user_orders(db=db, user_id=request.user.id, status=status)
    data = [GetOrderListItem.model_validate(order) for order in orders]
    return response_base.success(data=data)


@router.get('/{order_id}', summary='获取订单详情')
async def mall_get_order_detail(
    db: CurrentSession,
    order_id: Annotated[int, Path(description='订单 ID')],
) -> ResponseSchemaModel[GetOrderDetail]:
    """获取订单详情"""
    order = await order_service.get_order(db=db, order_id=order_id)
    return response_base.success(data=GetOrderDetail.model_validate(order))


@router.post('/{order_id}/pay', summary='支付订单', dependencies=[DependsJwtAuth])
async def mall_pay_order(
    request: Request,
    db: CurrentSessionTransaction,
    order_id: Annotated[int, Path(description='订单 ID')],
) -> ResponseSchemaModel[GetOrderDetail]:
    """支付订单（模拟支付）"""
    order = await order_service.pay_order(db=db, order_id=order_id, user_id=request.user.id)
    return response_base.success(data=GetOrderDetail.model_validate(order))


@router.post('/{order_id}/cancel', summary='取消订单', dependencies=[DependsJwtAuth])
async def mall_cancel_order(
    request: Request,
    db: CurrentSession,
    order_id: Annotated[int, Path(description='订单 ID')],
) -> ResponseSchemaModel[int]:
    """取消订单"""
    count = await order_service.cancel_order(db=db, order_id=order_id, user_id=request.user.id)
    return response_base.success(data=count)
