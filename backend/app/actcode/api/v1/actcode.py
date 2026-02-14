#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Path, Query

from backend.app.actcode.schema.actcode import (
    CreateBatchParam,
    GetActcodeDetail,
    GetBatchDetail,
    RedeemCodeParam,
    RedeemCodeResult,
    UpdateBatchParam,
)
from backend.app.actcode.service.actcode_service import actcode_service
from backend.common.pagination import DependsPagination, _CustomPageParams
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession
from backend.app.actcode.service.activate_service import activate_service

router = APIRouter(prefix='/actcode', tags=['激活码系统'])


@router.post('/batch', summary='创建批次', dependencies=[DependsJwtAuth])
async def create_batch(
    db: CurrentSession,
    obj: CreateBatchParam,
) -> ResponseSchemaModel[GetBatchDetail]:
    """创建批次并生成激活码"""
    data = await actcode_service.create_batch(db=db, obj=obj)
    return response_base.success(data=data)


@router.get('/batch', summary='获取批次列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_batch_list(
    db: CurrentSession,
    page_params: Annotated[_CustomPageParams, DependsPagination],
    app_id: Annotated[str | None, Query(description='应用 ID')] = None,
    status: Annotated[int | None, Query(description='状态')] = None,
    batch_no: Annotated[str | None, Query(description='批次编号')] = None,
) -> ResponseModel:
    """获取批次列表"""
    data = await actcode_service.get_batch_list(db=db, app_id=app_id, status=status, batch_no=batch_no)
    return response_base.success(data=data)


@router.get('/batch/{pk}', summary='获取批次详情', dependencies=[DependsJwtAuth])
async def get_batch(
    db: CurrentSession,
    pk: Annotated[int, Path(description='批次 ID')],
) -> ResponseSchemaModel[GetBatchDetail]:
    """获取批次详情"""
    data = await actcode_service.get_batch(db=db, pk=pk)
    return response_base.success(data=data)


@router.put('/batch/{pk}', summary='更新批次', dependencies=[DependsJwtAuth])
async def update_batch(
    db: CurrentSession,
    pk: Annotated[int, Path(description='批次 ID')],
    obj: UpdateBatchParam,
) -> ResponseModel:
    """更新批次"""
    await actcode_service.update_batch(db=db, pk=pk, obj=obj)
    return response_base.success()


@router.get('/codes', summary='获取激活码列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_code_list(
    db: CurrentSession,
    page_params: Annotated[_CustomPageParams, DependsPagination],
    batch_id: Annotated[int | None, Query(description='批次 ID')] = None,
    status: Annotated[int | None, Query(description='状态')] = None,
) -> ResponseModel:
    """获取激活码列表"""
    data = await actcode_service.get_code_list(db=db, batch_id=batch_id, status=status)
    return response_base.success(data=data)


@router.post('/redeem', summary='兑换激活码')
async def redeem_code(
    db: CurrentSession,
    obj: RedeemCodeParam,
) -> ResponseSchemaModel[RedeemCodeResult]:
    """兑换激活码，此接口供所有应用调用，无需认证"""
    data = await actcode_service.redeem_code(db=db, obj=obj)
    return response_base.success(data=data)


@router.get('/usage', summary='获取使用记录', dependencies=[DependsJwtAuth, DependsPagination])
async def get_usage_list(
    db: CurrentSession,
    page_params: Annotated[_CustomPageParams, DependsPagination],
    app_id: Annotated[str | None, Query(description='应用 ID')] = None,
    user_id: Annotated[str | None, Query(description='用户 ID')] = None,
    code_id: Annotated[int | None, Query(description='激活码 ID')] = None,
) -> ResponseModel:
    """获取使用记录列表"""
    data = await actcode_service.get_usage_list(db=db, app_id=app_id, user_id=user_id, code_id=code_id)
    return response_base.success(data=data)


@router.post('/agiso/activate', summary='通过阿奇索订单号激活账户')
async def activate_by_agiso_order(
    order_no: Annotated[str, Form(description='订单号（即激活码）')],
    username: Annotated[str, Form(description='用户名')],
    password: Annotated[str, Form(description='密码')],
) -> ResponseModel:
    """
    用户通过阿奇索订单号激活账户

    无需登录，用户提交订单号、用户名、密码即可创建账户

    :param order_no: 订单号
    :param username: 用户名
    :param password: 密码
    :return:
    """
    result = await activate_service.activate_by_order(order_no, username, password)
    return response_base.success(data=result)
