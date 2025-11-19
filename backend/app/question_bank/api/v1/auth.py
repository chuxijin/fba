#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.question_bank.crud.crud_user import user_account_dao
from backend.app.question_bank.schema.auth import (
    GetUserAccountDetail,
    TestLoginParam,
    WxLoginParam,
    WxLoginResponse,
)
from backend.app.question_bank.security import DependsCustomerAuth
from backend.app.question_bank.service.auth_service import auth_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.auth_strategy import AuthUser
from backend.database.db import CurrentSessionTransaction

router = APIRouter()


@router.post('/wx-login', summary='微信登录', name='qbank_wx_login')
async def wx_login(db: CurrentSessionTransaction, obj: WxLoginParam) -> ResponseSchemaModel[WxLoginResponse]:
    """
    微信登录

    支持小程序和 H5 平台，支持手机号绑定
    """
    access_token, user = await auth_service.wx_login(
        db=db,
        code=obj.code,
        platform=obj.platform,
        nickname=obj.nickname,
        avatar=obj.avatar,
        encrypted_data=obj.encrypted_data,
        iv=obj.iv,
    )

    user_info = GetUserAccountDetail.model_validate(user)

    data = WxLoginResponse(access_token=access_token, user_info=user_info)

    return response_base.success(data=data)


@router.post('/test-login', summary='测试登录', name='qbank_test_login')
async def test_login(db: CurrentSessionTransaction, obj: TestLoginParam) -> ResponseSchemaModel[WxLoginResponse]:
    """
    测试登录（仅用于开发测试）

    无需微信 code，直接用用户名登录，不存在则自动创建
    """
    access_token, user = await auth_service.test_login(db=db, username=obj.username, nickname=obj.nickname)

    user_info = GetUserAccountDetail.model_validate(user)

    data = WxLoginResponse(access_token=access_token, user_info=user_info)

    return response_base.success(data=data)


@router.get('/me', summary='获取当前用户信息', name='qbank_get_current_user')
async def get_current_user(
    db: CurrentSessionTransaction, current_user: AuthUser = DependsCustomerAuth
) -> ResponseSchemaModel[GetUserAccountDetail]:
    """
    获取当前用户信息

    需要登录认证
    """
    # 从数据库重新加载完整用户信息
    user = await user_account_dao.get(db, current_user.user_id)
    if not user:
        from backend.common.exception import errors

        raise errors.NotFoundError(msg='用户不存在')

    user_info = GetUserAccountDetail.model_validate(user)
    return response_base.success(data=user_info)
