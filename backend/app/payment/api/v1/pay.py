#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import JSONResponse

from backend.app.payment.schema.pay import (
    CreatePrepayParam,
    MallPrepayParam,
    MallRefundParam,
    PrepayResult,
    RefundResult,
)
from backend.app.payment.service.pay_service import pay_service
from backend.app.mall.crud.crud_order import order_dao
from backend.common.exception import errors
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(prefix='/pay', tags=['支付管理'])


@router.post('/prepay', summary='预下单', dependencies=[DependsJwtAuth])
async def pay_prepay(
    request: Request,
    db: CurrentSessionTransaction,
    obj: MallPrepayParam,
) -> ResponseSchemaModel[PrepayResult]:
    """商城预下单，返回前端拉起支付所需参数"""
    order = await order_dao.get(db, obj.order_id)
    if not order:
        raise errors.NotFoundError(msg='订单不存在')
    if order.user_id != request.user.id:
        raise errors.ForbiddenError(msg='无权操作该订单')
    if order.status != 'pending':
        raise errors.ForbiddenError(msg='订单状态不允许支付')

    # 更新订单的支付方式
    await order_dao.update_model(db, order.id, {'pay_type': obj.pay_type})

    params = CreatePrepayParam(
        order_no=order.order_no,
        biz_type='mall_order',
        pay_type=obj.pay_type,
        amount=order.total_amount,
        product_name=order.product_name,
        user_id=request.user.id,
        openid=obj.openid,
        payer_ip=obj.payer_ip,
    )
    data = await pay_service.create_prepay(db=db, params=params)
    return response_base.success(data=data)


@router.post('/notify', summary='微信支付回调')
async def pay_notify(request: Request, db: CurrentSessionTransaction) -> JSONResponse:
    """微信支付结果通知，无需认证"""
    headers = dict(request.headers)
    body = await request.body()

    try:
        await pay_service.handle_pay_callback(db=db, headers=headers, body=body)
        return JSONResponse(content={'code': 'SUCCESS', 'message': 'OK'})
    except Exception as e:
        return JSONResponse(content={'code': 'FAIL', 'message': str(e)}, status_code=500)


@router.post('/refund-notify', summary='微信退款回调')
async def pay_refund_notify(request: Request, db: CurrentSessionTransaction) -> JSONResponse:
    """微信退款结果通知，无需认证"""
    headers = dict(request.headers)
    body = await request.body()

    try:
        await pay_service.handle_refund_callback(db=db, headers=headers, body=body)
        return JSONResponse(content={'code': 'SUCCESS', 'message': 'OK'})
    except Exception as e:
        return JSONResponse(content={'code': 'FAIL', 'message': str(e)}, status_code=500)


@router.get('/query/{order_no}', summary='查询支付状态', dependencies=[DependsJwtAuth])
async def pay_query(
    request: Request,
    db: CurrentSession,
    order_no: Annotated[str, Path(description='业务订单号')],
) -> ResponseModel:
    """主动查询订单的支付状态"""
    data = await pay_service.query_payment(db=db, order_no=order_no, user_id=request.user.id)
    return response_base.success(data=data)


@router.post('/refund', summary='申请退款', dependencies=[DependsJwtAuth])
async def pay_refund(
    request: Request,
    db: CurrentSessionTransaction,
    obj: MallRefundParam,
) -> ResponseSchemaModel[RefundResult]:
    """申请订单退款"""
    order = await order_dao.get(db, obj.order_id)
    if not order:
        raise errors.NotFoundError(msg='订单不存在')

    data = await pay_service.refund(
        db=db,
        order_no=order.order_no,
        user_id=request.user.id,
        refund_amount=obj.refund_amount,
        reason=obj.reason,
    )
    return response_base.success(data=RefundResult(**data))


@router.get('/list', summary='支付记录列表', dependencies=[DependsJwtAuth])
async def pay_list(
    request: Request,
    db: CurrentSession,
    status: Annotated[str | None, Query(description='状态过滤')] = None,
) -> ResponseModel:
    """获取用户的支付记录列表"""
    from backend.app.payment.crud.crud_pay_transaction import pay_transaction_dao

    records = await pay_transaction_dao.get_by_user(db, request.user.id, status=status)
    data = [
        {
            'transaction_no': r.transaction_no,
            'order_no': r.order_no,
            'biz_type': r.biz_type,
            'pay_type': r.pay_type,
            'amount': str(r.amount),
            'status': r.status,
            'trade_no': r.trade_no,
            'product_name': r.product_name,
            'paid_time': r.paid_time,
            'created_time': r.created_time,
        }
        for r in records
    ]
    return response_base.success(data=data)
