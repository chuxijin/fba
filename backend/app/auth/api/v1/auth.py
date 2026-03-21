#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.auth.crud.crud_social_account import social_account_dao
from backend.app.auth.schema.auth import (
    GetAuthUserDetail,
    GetSocialAccountBrief,
    LoginResponse,
    TestLoginParam,
    WxLoginParam,
)
from backend.app.auth.security import DependsCurrentUser
from backend.app.auth.service.auth_service import unified_auth_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.auth_strategy import AuthUser
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.post('/wx-login', summary='微信登录')
async def wx_login(
    db: CurrentSessionTransaction,
    obj: WxLoginParam,
) -> ResponseSchemaModel[LoginResponse]:
    """微信登录（支持小程序/H5/公众号）"""
    access_token, sys_user, social = await unified_auth_service.wx_login(
        db=db,
        code=obj.code,
        platform=obj.platform,
        nickname=obj.nickname,
        avatar=obj.avatar,
        encrypted_data=obj.encrypted_data,
        iv=obj.iv,
    )

    user_info = GetAuthUserDetail(
        id=sys_user.id,
        username=sys_user.username,
        nickname=sys_user.nickname or '微信用户',
        avatar=sys_user.avatar,
        phone=sys_user.phone,
        open_id=social.openid if social else None,
        status=sys_user.status,
    )

    return response_base.success(data=LoginResponse(access_token=access_token, user_info=user_info))


@router.post('/test-login', summary='测试登录')
async def test_login(
    db: CurrentSessionTransaction,
    obj: TestLoginParam,
) -> ResponseSchemaModel[LoginResponse]:
    """测试登录（仅用于开发测试）"""
    access_token, sys_user, social = await unified_auth_service.test_login(
        db=db, username=obj.username, nickname=obj.nickname
    )

    user_info = GetAuthUserDetail(
        id=sys_user.id,
        username=sys_user.username,
        nickname=sys_user.nickname or '微信用户',
        avatar=sys_user.avatar,
        phone=sys_user.phone,
        open_id=social.openid if social else None,
        status=sys_user.status,
    )

    return response_base.success(data=LoginResponse(access_token=access_token, user_info=user_info))


@router.get('/me', summary='获取当前用户信息')
async def get_current_user_info(
    db: CurrentSession,
    current_user: AuthUser = DependsCurrentUser,
) -> ResponseSchemaModel[GetAuthUserDetail]:
    """获取当前用户信息"""
    from sqlalchemy import select

    from backend.app.admin.model import User

    stmt = select(User).where(User.id == current_user.user_id)
    result = await db.execute(stmt)
    sys_user = result.scalar_one_or_none()
    if not sys_user:
        from backend.common.exception import errors

        raise errors.NotFoundError(msg='用户不存在')

    # 获取 openid
    open_id = await social_account_dao.get_user_openid(db, sys_user.id, 'wechat_miniapp')

    user_info = GetAuthUserDetail(
        id=sys_user.id,
        username=sys_user.username,
        nickname=sys_user.nickname or '微信用户',
        avatar=sys_user.avatar,
        phone=sys_user.phone,
        open_id=open_id,
        status=sys_user.status,
    )
    return response_base.success(data=user_info)


@router.get('/me/socials', summary='获取社交绑定列表')
async def get_my_socials(
    db: CurrentSession,
    current_user: AuthUser = DependsCurrentUser,
) -> ResponseSchemaModel[list[GetSocialAccountBrief]]:
    """获取当前用户的所有社交绑定"""
    socials = await social_account_dao.get_by_user_id(db, current_user.user_id)
    data = [GetSocialAccountBrief.model_validate(s) for s in socials]
    return response_base.success(data=data)
