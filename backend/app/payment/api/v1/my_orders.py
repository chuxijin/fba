#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.payment.schema.my_orders import MyOrderActionParam, MyOrderItem, MyOrderPage, MyOrderQuery
from backend.app.payment.service.my_order_service import my_order_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(prefix='/pay/orders/my', tags=['我的订单'], dependencies=[DependsJwtAuth])
OrderNo = Annotated[str, Path(min_length=1, max_length=64)]


@router.get('/page', summary='筛选我的订单')
async def list_my_orders(
    request: Request, db: CurrentSession, query: Annotated[MyOrderQuery, Query()]
) -> ResponseSchemaModel[MyOrderPage]:
    return response_base.success(data=await my_order_service.page(db, request.user.id, query))


@router.get('/{order_no}', summary='查看我的订单详情')
async def get_my_order(request: Request, db: CurrentSession, order_no: OrderNo) -> ResponseSchemaModel[MyOrderItem]:
    return response_base.success(
        data=await my_order_service.detail(db, request.user.id, order_no)
    )


@router.post('/{order_no}/refresh', summary='核对我的订单状态')
async def refresh_my_order(
    request: Request, db: CurrentSessionTransaction, order_no: OrderNo, obj: MyOrderActionParam
) -> ResponseSchemaModel[MyOrderItem]:
    return response_base.success(data=await my_order_service.refresh(db, request.user.id, order_no, obj.wx_code))


@router.post('/{order_no}/close', summary='关闭我的待支付订单记录')
async def close_my_order(
    request: Request, db: CurrentSessionTransaction, order_no: OrderNo, obj: MyOrderActionParam
) -> ResponseSchemaModel[MyOrderItem]:
    return response_base.success(data=await my_order_service.close(db, request.user.id, order_no, obj.wx_code))


@router.delete('/{order_no}', summary='从用户列表移除终态订单，不删除交易')
async def remove_my_order(request: Request, db: CurrentSessionTransaction, order_no: OrderNo) -> ResponseModel:
    await my_order_service.remove(db, request.user.id, order_no)
    return response_base.success()
