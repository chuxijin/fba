#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Literal

from fastapi import Depends, Request

from backend.common.exception import errors
from backend.common.security.auth_strategy import AuthUser


async def get_current_user(request: Request) -> tuple[Literal['customer', 'admin'], AuthUser | None]:
    """
    获取当前用户（客户或管理员）

    :param request: 请求对象
    :return: (用户类型, 用户对象) 元组
    """
    # 新格式：从 request.state 获取（由中间件设置）
    if hasattr(request.state, 'auth_user'):
        user: AuthUser = request.state.auth_user
        return (user.user_type, user)

    # 旧格式：Admin 用户（向后兼容）
    if hasattr(request, 'user') and request.user:
        return ('admin', None)

    raise errors.AuthorizationError(msg='未登录')


async def get_current_customer(request: Request) -> AuthUser:
    """
    获取当前客户用户（仅客户）

    :param request: 请求对象
    :return:
    """
    user_type, user = await get_current_user(request)

    if user_type != 'customer':
        raise errors.AuthorizationError(msg='需要客户身份')

    return user


async def get_optional_customer(request: Request) -> AuthUser | None:
    """
    可选的客户认证（允许未登录）

    :param request: 请求对象
    :return:
    """
    try:
        return await get_current_customer(request)
    except errors.AuthorizationError:
        return None


# 依赖注入快捷方式
DependsCurrentUser = Depends(get_current_user)
DependsCustomerAuth = Depends(get_current_customer)
DependsOptionalCustomerAuth = Depends(get_optional_customer)

