#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一 Token 管理工具

为所有用户类型提供统一的 token 创建、验证和刷新机制
"""
import json
from datetime import timedelta
from typing import Any
from uuid import uuid4

from jose import ExpiredSignatureError, JWTError, jwt
from pydantic import BaseModel

from backend.common.exception import errors
from backend.common.security.auth_strategy import AuthUser, get_user_loader, load_user_by_type
from backend.core.conf import settings
from backend.database.redis import redis_client
from backend.utils.timezone import timezone


class UnifiedTokenPayload(BaseModel):
    """统一的 Token Payload"""

    user_id: int
    user_type: str
    session_uuid: str
    expire_time: int


class UnifiedAccessToken(BaseModel):
    """统一的访问令牌"""

    access_token: str
    access_token_expire_time: int
    session_uuid: str
    user_type: str


async def create_unified_token(
    user_id: int,
    user_type: str,
    *,
    multi_login: bool = True,
    **extra_info: Any,
) -> UnifiedAccessToken:
    """
    创建统一的访问令牌（所有用户类型通用）

    :param user_id: 用户 ID
    :param user_type: 用户类型（admin, customer, software, etc.）
    :param multi_login: 是否允许多端登录
    :param extra_info: 额外信息（存储在 Redis）
    :return:
    """
    # 获取用户加载器
    loader = get_user_loader(user_type)
    if not loader:
        raise errors.AuthorizationError(msg=f'不支持的用户类型: {user_type}')

    # 生成 token
    expire = timezone.now() + timedelta(seconds=settings.TOKEN_EXPIRE_SECONDS)
    session_uuid = str(uuid4())

    payload = {
        'user_id': user_id,
        'user_type': user_type,
        'session_uuid': session_uuid,
        'exp': timezone.to_utc(expire).timestamp(),
        'iat': timezone.now().timestamp(),
    }

    access_token = jwt.encode(payload, settings.TOKEN_SECRET_KEY, algorithm=settings.TOKEN_ALGORITHM)

    # 使用类型特定的 Redis 前缀
    redis_prefix = loader.get_redis_prefix()

    # 如果不允许多端登录，删除该用户的所有旧 token
    if not multi_login:
        await redis_client.delete_prefix(f'{redis_prefix}:{user_id}')

    # 存储 token
    await redis_client.setex(
        f'{redis_prefix}:{user_id}:{session_uuid}', settings.TOKEN_EXPIRE_SECONDS, access_token
    )

    # 存储额外信息
    if extra_info:
        await redis_client.setex(
            f'{settings.TOKEN_EXTRA_INFO_REDIS_PREFIX}:{user_type}:{user_id}:{session_uuid}',
            settings.TOKEN_EXPIRE_SECONDS,
            json.dumps(extra_info, ensure_ascii=False),
        )

    return UnifiedAccessToken(
        access_token=access_token,
        access_token_expire_time=int(expire.timestamp()),
        session_uuid=session_uuid,
        user_type=user_type,
    )


async def verify_unified_token(token: str) -> AuthUser:
    """
    验证统一令牌并加载用户信息

    :param token: JWT Token
    :return:
    """
    try:
        # 解析 token
        payload = jwt.decode(token, settings.TOKEN_SECRET_KEY, algorithms=[settings.TOKEN_ALGORITHM])

        # 尝试读取新格式字段
        user_id = payload.get('user_id')
        user_type = payload.get('user_type')
        session_uuid = payload.get('session_uuid')

        # 如果缺少 user_id，尝试旧格式的 'sub'
        if not user_id:
            user_id = payload.get('sub')
            if user_id:
                user_id = int(user_id)  # sub 是字符串，需要转换

        # 如果没有 user_type，可能是旧格式 admin token
        # 这种情况让中间件的回退逻辑处理
        if not user_type:
            raise errors.TokenError(msg='Token 格式无效：缺少 user_type')

        if not user_id or not session_uuid:
            raise errors.TokenError(msg='Token 格式无效')

        # 获取加载器
        loader = get_user_loader(user_type)
        if not loader:
            raise errors.TokenError(msg=f'不支持的用户类型: {user_type}')

        # 验证 token 是否在 Redis 中
        redis_prefix = loader.get_redis_prefix()
        redis_token = await redis_client.get(f'{redis_prefix}:{user_id}:{session_uuid}')

        if not redis_token:
            raise errors.TokenError(msg='Token 已过期')

        if token != redis_token:
            raise errors.TokenError(msg='Token 已失效')

        # 加载用户信息
        user = await load_user_by_type(user_type, user_id)
        if not user:
            raise errors.TokenError(msg='用户不存在')

        return user

    except ExpiredSignatureError:
        raise errors.TokenError(msg='Token 已过期')
    except JWTError:
        raise errors.TokenError(msg='Token 无效')


async def revoke_unified_token(user_id: int, user_type: str, session_uuid: str) -> None:
    """
    撤销统一令牌

    :param user_id: 用户 ID
    :param user_type: 用户类型
    :param session_uuid: 会话 UUID
    :return:
    """
    loader = get_user_loader(user_type)
    if not loader:
        return

    redis_prefix = loader.get_redis_prefix()
    await redis_client.delete(f'{redis_prefix}:{user_id}:{session_uuid}')
    await redis_client.delete(f'{settings.TOKEN_EXTRA_INFO_REDIS_PREFIX}:{user_type}:{user_id}:{session_uuid}')


async def refresh_unified_token(
    old_token: str,
    *,
    multi_login: bool = True,
    **extra_info: Any,
) -> UnifiedAccessToken:
    """
    刷新统一令牌

    :param old_token: 旧的 token
    :param multi_login: 是否允许多端登录
    :param extra_info: 额外信息
    :return:
    """
    # 验证旧 token（不检查过期时间）
    try:
        payload = jwt.decode(
            old_token, settings.TOKEN_SECRET_KEY, algorithms=[settings.TOKEN_ALGORITHM], options={'verify_exp': False}
        )

        user_id = payload.get('user_id')
        user_type = payload.get('user_type')
        old_session_uuid = payload.get('session_uuid')

        if not user_id or not user_type or not old_session_uuid:
            raise errors.TokenError(msg='Token 格式无效')

        # 撤销旧 token
        await revoke_unified_token(user_id, user_type, old_session_uuid)

        # 创建新 token
        return await create_unified_token(user_id, user_type, multi_login=multi_login, **extra_info)

    except JWTError:
        raise errors.TokenError(msg='Token 无效')
