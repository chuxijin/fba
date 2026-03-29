#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request, Response
from starlette.background import BackgroundTasks

from backend.app.actcode.schema.actcode import (
    CreateBatchParam,
    GetBatchDetail,
    OrderCodeActivateResult,
    OrderCodeLoginResult,
    OrderCodePayload,
    OrderCodeVerifyResult,
    RedeemCodeParam,
    RedeemCodeResult,
    UpdateBatchParam,
)
from backend.app.actcode.service.actcode_service import actcode_service
from backend.app.actcode.service.activate_service import activate_service
from backend.common.pagination import DependsPagination, _CustomPageParams
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

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


@router.post('/agiso/login', summary='通过订单号登录')
async def login_by_agiso_order(
    db: CurrentSessionTransaction,
    response: Response,
    obj: OrderCodePayload,
    background_tasks: BackgroundTasks,
) -> ResponseSchemaModel[OrderCodeLoginResult]:
    """
    通过订单号直接登录，未绑定时自动创建账号并开通权益

    :param db: 数据库会话
    :param response: FastAPI 响应对象
    :param obj: 订单号参数
    :param background_tasks: 后台任务
    :return:
    """
    result = await activate_service.login_by_order(
        db=db,
        order_input=obj.order_input,
        response=response,
        background_tasks=background_tasks,
    )
    return response_base.success(data=result)


@router.post('/agiso/activate', summary='已登录用户当前账号激活订单号', dependencies=[DependsJwtAuth])
async def activate_agiso_order_for_current_user(
    request: Request,
    db: CurrentSessionTransaction,
    obj: OrderCodePayload,
) -> ResponseSchemaModel[OrderCodeActivateResult]:
    """
    将订单号绑定到当前登录账号

    :param request: FastAPI 请求对象
    :param db: 数据库会话
    :param obj: 订单号参数
    :return:
    """
    result = await activate_service.activate_current_user(
        db=db,
        order_input=obj.order_input,
        current_user=request.user,
    )
    return response_base.success(data=result)


@router.post('/agiso/verify', summary='验证订单号是否有效')
async def verify_order_no(
    db: CurrentSession,
    obj: OrderCodePayload,
) -> ResponseSchemaModel[OrderCodeVerifyResult]:
    """
    验证用户输入中是否包含有效的订单号

    :param db: 数据库会话
    :param obj: 订单号参数
    :return:
    """
    result = await activate_service.verify_order(db=db, order_input=obj.order_input)
    return response_base.success(data=result)
