#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import random

from fastapi import APIRouter, Body, Depends, Request, Response
from pyrate_limiter import Duration, Rate
from starlette.background import BackgroundTasks

from backend.app.admin.schema.token import GetLoginToken
from backend.app.admin.schema.user import ChangePhoneParam, SmsLoginParam
from backend.app.admin.service.auth_service import auth_service
from backend.app.admin.service.user_service import user_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.core.conf import settings
from backend.database.db import CurrentSessionTransaction
from backend.database.redis import redis_client
from backend.plugin.sms.schema.sms import SendSmsRequest, SendSmsResponse
from backend.plugin.sms.service.sms_service import sms_service
from backend.utils.limiter import RateLimiter

router = APIRouter()


@router.post('/send', summary='发送短信验证码', dependencies=[DependsJwtAuth])
async def send_sms(request: SendSmsRequest = Body(...)) -> ResponseSchemaModel[SendSmsResponse]:
    """发送短信验证码（调试）"""
    result = await sms_service.send_sms(
        phone_numbers=request.phone_numbers,
        template_id=request.template_id,
        template_params=request.template_params,
        sign_name=request.sign_name,
        sms_sdk_app_id=request.sms_sdk_app_id,
        extend_code=request.extend_code,
        session_context=request.session_context,
        sender_id=request.sender_id,
    )
    return response_base.success(data=result)


@router.post(
    '/send_login_code',
    summary='发送登录短信验证码',
    dependencies=[Depends(RateLimiter(Rate(1, Duration.MINUTE)))],
)
async def send_login_code(phone: str = Body(..., embed=True)) -> ResponseSchemaModel:
    """发送登录短信验证码，生成 6 位验证码，存储在 Redis 中"""
    verification_code = ''.join(random.choices('0123456789', k=6))

    await redis_client.set(
        f'{settings.SMS_LOGIN_REDIS_PREFIX}:{phone}',
        verification_code,
        ex=settings.SMS_LOGIN_EXPIRE_SECONDS,
    )

    await sms_service.send_sms(
        phone_numbers=[phone],
        template_id=settings.SMS_LOGIN_TEMPLATE_ID,
        template_params=[verification_code],
        sign_name=settings.SMS_SIGN_NAME,
        sms_sdk_app_id=settings.SMS_SDK_APP_ID,
    )
    return response_base.success(data=f'验证码已发送到手机 {phone}')


@router.post(
    '/login/sms',
    summary='短信验证码登录',
    description='使用手机号和短信验证码登录，用户不存在则自动注册',
    dependencies=[Depends(RateLimiter(Rate(5, Duration.MINUTE)))],
)
async def login_by_sms(
    request: Request,
    response: Response,
    db: CurrentSessionTransaction,
    obj: SmsLoginParam,
    background_tasks: BackgroundTasks,
) -> ResponseSchemaModel[GetLoginToken]:
    """短信验证码登录"""
    data = await auth_service.login_by_sms(
        db=db,
        response=response,
        obj=obj,
        background_tasks=background_tasks,
    )
    return response_base.success(data=data)


@router.post(
    '/phone/send-code',
    summary='发送更换手机号验证码',
    dependencies=[DependsJwtAuth, Depends(RateLimiter(Rate(1, Duration.MINUTE)))],
)
async def send_change_phone_code(phone: str = Body(..., embed=True)) -> ResponseSchemaModel:
    """发送更换手机号的验证码（需登录）"""
    verification_code = ''.join(random.choices('0123456789', k=6))

    await redis_client.set(
        f'{settings.SMS_PHONE_CHANGE_REDIS_PREFIX}:{phone}',
        verification_code,
        ex=settings.SMS_LOGIN_EXPIRE_SECONDS,
    )

    await sms_service.send_sms(
        phone_numbers=[phone],
        template_id=settings.SMS_LOGIN_TEMPLATE_ID,
        template_params=[verification_code],
        sign_name=settings.SMS_SIGN_NAME,
        sms_sdk_app_id=settings.SMS_SDK_APP_ID,
    )
    return response_base.success(data=f'验证码已发送到手机 {phone}')


@router.put(
    '/phone/change',
    summary='更换手机号',
    description='已绑定手机需验证旧手机，首次绑定只需验证新手机',
    dependencies=[DependsJwtAuth],
)
async def change_phone(
    request: Request,
    db: CurrentSessionTransaction,
    obj: ChangePhoneParam,
) -> ResponseSchemaModel:
    """更换/绑定手机号"""
    await user_service.update_phone(
        db=db,
        user_id=request.user.id,
        old_phone_code=obj.old_phone_code,
        new_phone=obj.new_phone,
        new_phone_code=obj.new_phone_code,
    )
    return response_base.success(data='手机号更换成功')
