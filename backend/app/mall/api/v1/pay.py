#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Request
from fastapi.responses import JSONResponse

from backend.app.mall.schema.payment import PrepayParam, PrepayResult, RefundParam, RefundResult
from backend.app.mall.service.payment_service import payment_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(prefix='/pay', tags=['支付管理'])


@router.post('/prepay', summary='预下单', dependencies=[DependsJwtAuth])
async def pay_prepay(
    request: Request,
    db: CurrentSessionTransaction,
    obj: PrepayParam,
) -> ResponseSchemaModel[PrepayResult]:
    """预下单，返回前端拉起支付所需参数"""
    pay_params = await payment_service.prepay(
        db=db,
        order_id=obj.order_id,
        user_id=request.user.id,
        pay_type=obj.pay_type,
        openid=obj.openid,
        payer_ip=obj.payer_ip,
    )
    data = PrepayResult(pay_params=pay_params)
    return response_base.success(data=data)


@router.post('/notify', summary='微信支付回调')
async def pay_notify(request: Request, db: CurrentSessionTransaction) -> JSONResponse:
    """微信支付结果通知，无需认证"""
    headers = dict(request.headers)
    body = await request.body()

    try:
        await payment_service.handle_pay_callback(db=db, headers=headers, body=body)
        return JSONResponse(content={'code': 'SUCCESS', 'message': 'OK'})
    except Exception as e:
        return JSONResponse(content={'code': 'FAIL', 'message': str(e)}, status_code=500)


@router.post('/refund-notify', summary='微信退款回调')
async def pay_refund_notify(request: Request, db: CurrentSessionTransaction) -> JSONResponse:
    """微信退款结果通知，无需认证"""
    headers = dict(request.headers)
    body = await request.body()

    try:
        await payment_service.handle_refund_callback(db=db, headers=headers, body=body)
        return JSONResponse(content={'code': 'SUCCESS', 'message': 'OK'})
    except Exception as e:
        return JSONResponse(content={'code': 'FAIL', 'message': str(e)}, status_code=500)


@router.get('/query/{order_id}', summary='查询支付状态', dependencies=[DependsJwtAuth])
async def pay_query(
    request: Request,
    db: CurrentSession,
    order_id: Annotated[int, Path(description='订单 ID')],
) -> ResponseModel:
    """主动查询订单的支付状态"""
    data = await payment_service.query_payment(db=db, order_id=order_id, user_id=request.user.id)
    return response_base.success(data=data)


@router.post('/refund', summary='申请退款', dependencies=[DependsJwtAuth])
async def pay_refund(
    request: Request,
    db: CurrentSessionTransaction,
    obj: RefundParam,
) -> ResponseSchemaModel[RefundResult]:
    """申请订单退款"""
    data = await payment_service.refund(
        db=db,
        order_id=obj.order_id,
        user_id=request.user.id,
        refund_amount=obj.refund_amount,
        reason=obj.reason,
    )
    return response_base.success(data=RefundResult(**data))
