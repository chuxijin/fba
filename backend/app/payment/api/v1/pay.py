#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json

from typing import Annotated

from fastapi import APIRouter, Path, Query, Request
from fastapi.responses import JSONResponse, Response

from backend.app.payment.schema.pay import (
    PayOrderListItem,
    PaymentConfirmResult,
    RefundParam,
    RefundResult,
    SubscriptionPaymentConfirmParam,
    SubscriptionPrepayParam,
    SubscriptionPrepayResult,
)
from backend.app.payment.service.pay_order_service import pay_order_service
from backend.app.payment.service.pay_service import pay_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(prefix='/pay', tags=['支付管理'])


def _is_xml_callback(body: bytes) -> bool:
    """
    判断是否为微信虚拟支付 XML 推送

    :param body: 请求体
    :return:
    """
    return body.lstrip().startswith(b'<')


def _is_xpay_json_callback(body: bytes) -> bool:
    """
    判断是否为微信虚拟支付 JSON 推送

    :param body: 请求体
    :return:
    """
    try:
        data = json.loads(body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False

    event = data.get('Event') if isinstance(data, dict) else None
    return isinstance(event, str) and event.startswith('xpay_')


def _xml_cdata(value: str) -> str:
    """
    转义 XML CDATA 内容

    :param value: 原始文本
    :return:
    """
    return value.replace(']]>', ']]]]><![CDATA[>')


def _callback_success_response(body: bytes) -> Response:
    """
    生成支付回调成功响应

    :param body: 请求体
    :return:
    """
    if _is_xml_callback(body):
        return Response(
            content='<xml><ErrCode>0</ErrCode><ErrMsg><![CDATA[success]]></ErrMsg></xml>',
            media_type='application/xml',
        )
    if _is_xpay_json_callback(body):
        return JSONResponse(content={'ErrCode': 0, 'ErrMsg': 'success'})
    return JSONResponse(content={'code': 'SUCCESS', 'message': 'OK'})


def _callback_fail_response(body: bytes, message: str) -> Response:
    """
    生成支付回调失败响应

    :param body: 请求体
    :param message: 错误信息
    :return:
    """
    if _is_xml_callback(body):
        safe_message = _xml_cdata(message)
        return Response(
            content=f'<xml><ErrCode>1</ErrCode><ErrMsg><![CDATA[{safe_message}]]></ErrMsg></xml>',
            media_type='application/xml',
            status_code=500,
        )
    if _is_xpay_json_callback(body):
        return JSONResponse(content={'ErrCode': 1, 'ErrMsg': message}, status_code=500)
    return JSONResponse(content={'code': 'FAIL', 'message': message}, status_code=500)


@router.post('/subscription/prepay', summary='订阅套餐预下单', dependencies=[DependsJwtAuth])
async def subscription_prepay(
    request: Request,
    db: CurrentSessionTransaction,
    obj: SubscriptionPrepayParam,
) -> ResponseSchemaModel[SubscriptionPrepayResult]:
    """订阅套餐预下单，返回前端拉起虚拟支付所需参数"""
    data = await pay_order_service.create_subscription_prepay(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.post('/subscription/confirm', summary='确认订阅支付状态', dependencies=[DependsJwtAuth])
async def subscription_confirm(
    request: Request,
    db: CurrentSessionTransaction,
    obj: SubscriptionPaymentConfirmParam,
) -> ResponseSchemaModel[PaymentConfirmResult]:
    """确认订阅支付状态，支付成功时发放权益"""
    data = await pay_order_service.confirm_subscription_payment(db=db, user_id=request.user.id, obj=obj)
    return response_base.success(data=data)


@router.post('/notify', summary='微信支付回调', response_model=None)
async def pay_notify(request: Request, db: CurrentSessionTransaction) -> Response:
    """微信支付结果通知，无需认证"""
    headers = dict(request.headers)
    body = await request.body()

    try:
        await pay_service.handle_pay_callback(db=db, headers=headers, body=body)
        return _callback_success_response(body)
    except Exception as e:
        return _callback_fail_response(body, str(e))


@router.post('/refund-notify', summary='微信退款回调', response_model=None)
async def pay_refund_notify(request: Request, db: CurrentSessionTransaction) -> Response:
    """微信退款结果通知，无需认证"""
    headers = dict(request.headers)
    body = await request.body()

    try:
        await pay_service.handle_refund_callback(db=db, headers=headers, body=body)
        return _callback_success_response(body)
    except Exception as e:
        return _callback_fail_response(body, str(e))


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
    obj: RefundParam,
) -> ResponseSchemaModel[RefundResult]:
    """申请支付订单退款"""
    data = await pay_service.refund(
        db=db,
        order_no=obj.order_no,
        user_id=request.user.id,
        refund_amount=obj.refund_amount,
        reason=obj.reason,
    )
    return response_base.success(data=RefundResult(**data))


@router.get('/orders/my', summary='我的支付订单', dependencies=[DependsJwtAuth])
async def pay_order_list(
    request: Request,
    db: CurrentSession,
    status: Annotated[str | None, Query(description='状态过滤')] = None,
) -> ResponseSchemaModel[list[PayOrderListItem]]:
    """获取用户的支付业务订单列表"""
    from backend.app.payment.crud.crud_pay_order import pay_order_dao

    records = await pay_order_dao.get_by_user(db, request.user.id, status=status)
    data = [PayOrderListItem.model_validate(record) for record in records]
    return response_base.success(data=data)


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
