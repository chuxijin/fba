#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession
from backend.plugin.app_auth.schema.order import (
    CreateOrderParam,
    GetOrderDetail,
    UpdateOrderParam,
)
from backend.plugin.app_auth.service.order_service import order_service

router = APIRouter()


@router.post('', summary='创建订单', dependencies=[DependsRBAC])
async def create_order(obj: CreateOrderParam) -> ResponseSchemaModel[GetOrderDetail]:
    """
    创建新订单
    
    :param obj: 订单创建参数
    :return:
    """
    data = await order_service.create(obj=obj)
    return response_base.success(data=data)


@router.delete('/{pk}', summary='删除订单', dependencies=[DependsRBAC])
async def delete_order(pk: Annotated[int, Path(description='订单ID')]) -> ResponseModel:
    """
    删除订单
    
    :param pk: 订单ID
    :return:
    """
    count = await order_service.delete(pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.put('/{pk}', summary='更新订单', dependencies=[DependsRBAC])
async def update_order(
    pk: Annotated[int, Path(description='订单ID')], obj: UpdateOrderParam
) -> ResponseModel:
    """
    更新订单信息
    
    :param pk: 订单ID
    :param obj: 订单更新参数
    :return:
    """
    count = await order_service.update(pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.get('', summary='分页获取订单列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_pagination_orders(
    db: CurrentSession,
    order_no: Annotated[str | None, Query(description='订单号')] = None,
    package_id: Annotated[int | None, Query(description='套餐ID')] = None,
    device_id: Annotated[int | None, Query(description='设备ID')] = None,
    status: Annotated[int | None, Query(description='订单状态')] = None,
) -> ResponseModel:
    """
    分页获取订单列表
    
    :param db: 数据库会话
    :param order_no: 订单号
    :param package_id: 套餐ID
    :param device_id: 设备ID
    :param status: 订单状态
    :return:
    """
    select = order_service.get_select(order_no=order_no, package_id=package_id, device_id=device_id, status=status)
    page_data = await paging_data(db, select)
    return response_base.success(data=page_data)


@router.get('/{pk}', summary='获取订单详情', dependencies=[DependsJwtAuth])
async def get_order(pk: Annotated[int, Path(description='订单ID')]) -> ResponseSchemaModel[GetOrderDetail]:
    """
    获取订单详情
    
    :param pk: 订单ID
    :return:
    """
    data = await order_service.get(pk=pk)
    return response_base.success(data=data) 