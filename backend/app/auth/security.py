#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import Depends, Request

from backend.common.exception import errors
from backend.common.security.auth_strategy import AuthUser


async def get_current_user(request: Request) -> AuthUser:
    """
    获取当前用户（基于统一认证，返回 sys_user.id）

    :param request: 请求对象
    :return:
    """
    # 新格式：由统一认证中间件设置
    if hasattr(request.state, 'auth_user'):
        return request.state.auth_user

    # 旧格式：Admin 用户（向后兼容）
    if hasattr(request, 'user') and request.user:
        legacy_user = request.user
        legacy_id = getattr(legacy_user, 'id', None) or getattr(legacy_user, 'user_id', None)
        legacy_name = getattr(legacy_user, 'username', None)
        if legacy_id:
            return AuthUser(user_id=int(legacy_id), user_type='admin', username=legacy_name)

    raise errors.AuthorizationError(msg='未登录')


# 依赖注入快捷方式（返回 sys_user.id 级别的身份）
DependsCurrentUser = Depends(get_current_user)
