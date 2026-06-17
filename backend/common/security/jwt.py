#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import uuid

from datetime import timedelta
from enum import StrEnum
from typing import Any

from fastapi import Depends, Request
from fastapi.security import HTTPBearer
from fastapi.security.utils import get_authorization_scheme_param
from jose import ExpiredSignatureError, JWTError, jwt
from pydantic_core import from_json
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.authentication import UnauthenticatedUser

from backend.app.admin.model import User
from backend.app.admin.schema.user import GetUserInfoWithRelationDetail
from backend.common.context import ctx
from backend.common.dataclasses import AccessToken, NewToken, RefreshToken, TokenPayload
from backend.common.exception import errors
from backend.core.conf import settings
from backend.database.db import async_db_session
from backend.database.redis import redis_client
from backend.utils.timezone import timezone

# JWT dependency injection
DependsJwtAuth = Depends(HTTPBearer())


class TokenInvalidReason(StrEnum):
    """Token 失效原因"""

    session_replaced = 'session_replaced'
    permission_changed = 'permission_changed'
    password_changed = 'password_changed'


TOKEN_INVALID_REASON_MESSAGES: dict[str, str] = {
    TokenInvalidReason.session_replaced.value: '账号已在其他设备登录，请重新登录',
    TokenInvalidReason.permission_changed.value: '登录状态已失效，请重新登录',
    TokenInvalidReason.password_changed.value: '密码已变更，请重新登录',
}


def _invalid_reason_key(user_id: int, session_uuid: str) -> str:
    """
    构造 token 失效原因 key

    :param user_id: 用户 ID
    :param session_uuid: 会话 UUID
    :return:
    """
    return f'{settings.TOKEN_INVALID_REASON_REDIS_PREFIX}:{user_id}:{session_uuid}'


def _refresh_invalid_reason_key(user_id: int, session_uuid: str) -> str:
    """
    构造 refresh token 失效原因 key

    :param user_id: 用户 ID
    :param session_uuid: 会话 UUID
    :return:
    """
    return f'{settings.TOKEN_REFRESH_INVALID_REASON_REDIS_PREFIX}:{user_id}:{session_uuid}'


def jwt_encode(payload: dict[str, Any]) -> str:
    """
    生成 JWT token

    :param payload: 载荷
    :return:
    """
    return jwt.encode(payload, settings.TOKEN_SECRET_KEY, settings.TOKEN_ALGORITHM)


async def mark_user_tokens_invalid(
    user_id: int,
    *,
    reason: TokenInvalidReason,
    token_prefix: str,
    reason_key_builder: Any,
    default_ttl_seconds: int,
    exclude_session_uuid: str | None = None,
) -> None:
    """
    标记用户当前 token 会话的失效原因

    :param user_id: 用户 ID
    :param reason: 失效原因
    :param token_prefix: token Redis key 前缀
    :param reason_key_builder: 失效原因 key 构造函数
    :param default_ttl_seconds: 默认 TTL 秒数
    :param exclude_session_uuid: 排除的会话 UUID
    :return:
    """
    keys = await redis_client.get_prefix(f'{token_prefix}:{user_id}:')
    for key in keys:
        session_uuid = key.rsplit(':', 1)[-1]
        if exclude_session_uuid and session_uuid == exclude_session_uuid:
            continue

        ttl = await redis_client.ttl(key)
        if ttl <= 0:
            ttl = default_ttl_seconds

        await redis_client.setex(reason_key_builder(user_id, session_uuid), ttl, reason.value)


async def mark_user_sessions_invalid(
    user_id: int,
    *,
    reason: TokenInvalidReason,
    exclude_session_uuid: str | None = None,
) -> None:
    """
    标记用户当前 access token 会话的失效原因

    :param user_id: 用户 ID
    :param reason: 失效原因
    :param exclude_session_uuid: 排除的会话 UUID
    :return:
    """
    await mark_user_tokens_invalid(
        user_id,
        reason=reason,
        token_prefix=settings.TOKEN_REDIS_PREFIX,
        reason_key_builder=_invalid_reason_key,
        default_ttl_seconds=settings.TOKEN_EXPIRE_SECONDS,
        exclude_session_uuid=exclude_session_uuid,
    )


async def mark_user_refresh_sessions_invalid(
    user_id: int,
    *,
    reason: TokenInvalidReason,
    exclude_session_uuid: str | None = None,
) -> None:
    """
    标记用户当前 refresh token 会话的失效原因

    :param user_id: 用户 ID
    :param reason: 失效原因
    :param exclude_session_uuid: 排除的会话 UUID
    :return:
    """
    await mark_user_tokens_invalid(
        user_id,
        reason=reason,
        token_prefix=settings.TOKEN_REFRESH_REDIS_PREFIX,
        reason_key_builder=_refresh_invalid_reason_key,
        default_ttl_seconds=settings.TOKEN_REFRESH_EXPIRE_SECONDS,
        exclude_session_uuid=exclude_session_uuid,
    )


async def mark_session_invalid(
    user_id: int,
    session_uuid: str,
    *,
    reason: TokenInvalidReason,
    token_key: str | None = None,
) -> None:
    """
    标记单个 access token 会话的失效原因

    :param user_id: 用户 ID
    :param session_uuid: 会话 UUID
    :param reason: 失效原因
    :param token_key: 已知的 token Redis key
    :return:
    """
    key = token_key or f'{settings.TOKEN_REDIS_PREFIX}:{user_id}:{session_uuid}'
    ttl = await redis_client.ttl(key)
    if ttl <= 0:
        ttl = settings.TOKEN_EXPIRE_SECONDS

    await redis_client.setex(_invalid_reason_key(user_id, session_uuid), ttl, reason.value)


async def get_token_invalid_message(user_id: int, session_uuid: str) -> str | None:
    """
    获取 token 失效提示

    :param user_id: 用户 ID
    :param session_uuid: 会话 UUID
    :return:
    """
    reason = await redis_client.get(_invalid_reason_key(user_id, session_uuid))
    if not reason:
        return None

    return TOKEN_INVALID_REASON_MESSAGES.get(reason, '登录状态已失效，请重新登录')


async def get_refresh_token_invalid_message(user_id: int, session_uuid: str) -> str | None:
    """
    获取 refresh token 失效提示

    :param user_id: 用户 ID
    :param session_uuid: 会话 UUID
    :return:
    """
    reason = await redis_client.get(_refresh_invalid_reason_key(user_id, session_uuid))
    if not reason:
        return None

    return TOKEN_INVALID_REASON_MESSAGES.get(reason, '登录状态已失效，请重新登录')


def jwt_decode(token: str) -> TokenPayload:
    """
    解析 JWT token

    :param token: JWT token
    :return:
    """
    try:
        payload = jwt.decode(
            token,
            settings.TOKEN_SECRET_KEY,
            algorithms=[settings.TOKEN_ALGORITHM],
            options={'verify_exp': True},
        )
        session_uuid = payload.get('session_uuid')
        user_id = payload.get('sub')
        expire = payload.get('exp')
        if not session_uuid or not user_id or not expire:
            raise errors.TokenError(msg='Token 无效')
    except ExpiredSignatureError:
        raise errors.TokenError(msg='Token 已过期')
    except (JWTError, Exception):
        raise errors.TokenError(msg='Token 无效')
    return TokenPayload(
        user_id=int(user_id),
        session_uuid=session_uuid,
        expire_time=timezone.from_datetime(timezone.to_utc(expire)),
    )


async def create_access_token(user_id: int, *, multi_login: bool, **kwargs) -> AccessToken:
    """
    生成加密 token

    :param user_id: 用户 ID
    :param multi_login: 是否允许多端登录
    :param kwargs: token 额外信息
    :return:
    """
    expire = timezone.now() + timedelta(seconds=settings.TOKEN_EXPIRE_SECONDS)
    session_uuid = str(uuid.uuid4())
    access_token = jwt_encode({
        'session_uuid': session_uuid,
        'exp': timezone.to_utc(expire).timestamp(),
        'sub': str(user_id),
    })

    if not multi_login:
        await mark_user_sessions_invalid(user_id, reason=TokenInvalidReason.session_replaced)
        await redis_client.delete_prefix(f'{settings.TOKEN_REDIS_PREFIX}:{user_id}')

    await redis_client.set(
        f'{settings.TOKEN_REDIS_PREFIX}:{user_id}:{session_uuid}',
        access_token,
        ex=settings.TOKEN_EXPIRE_SECONDS,
    )

    # Token 附加信息单独存储
    if kwargs:
        await redis_client.set(
            f'{settings.TOKEN_EXTRA_INFO_REDIS_PREFIX}:{user_id}:{session_uuid}',
            json.dumps(kwargs, ensure_ascii=False),
            ex=settings.TOKEN_EXPIRE_SECONDS,
        )

    return AccessToken(access_token=access_token, access_token_expire_time=expire, session_uuid=session_uuid)


async def create_refresh_token(session_uuid: str, user_id: int, *, multi_login: bool) -> RefreshToken:
    """
    生成加密刷新 token，仅用于创建新的 token

    :param session_uuid: 会话 UUID
    :param user_id: 用户 ID
    :param multi_login: 是否允许多端登录
    :return:
    """
    expire = timezone.now() + timedelta(seconds=settings.TOKEN_REFRESH_EXPIRE_SECONDS)
    refresh_token = jwt_encode({
        'session_uuid': session_uuid,
        'exp': timezone.to_utc(expire).timestamp(),
        'sub': str(user_id),
    })

    if not multi_login:
        await mark_user_refresh_sessions_invalid(user_id, reason=TokenInvalidReason.session_replaced)
        await redis_client.delete_prefix(f'{settings.TOKEN_REFRESH_REDIS_PREFIX}:{user_id}')

    await redis_client.set(
        f'{settings.TOKEN_REFRESH_REDIS_PREFIX}:{user_id}:{session_uuid}',
        refresh_token,
        ex=settings.TOKEN_REFRESH_EXPIRE_SECONDS,
    )
    return RefreshToken(refresh_token=refresh_token, refresh_token_expire_time=expire)


async def create_new_token(
    refresh_token: str,
    session_uuid: str,
    user_id: int,
    *,
    multi_login: bool,
    **kwargs,
) -> NewToken:
    """
    生成新的 token

    :param refresh_token: 刷新 token
    :param session_uuid: 会话 UUID
    :param user_id: 用户 ID
    :param multi_login: 是否允许多端登录
    :param kwargs: token 附加信息
    :return:
    """
    redis_refresh_token = await redis_client.get(f'{settings.TOKEN_REFRESH_REDIS_PREFIX}:{user_id}:{session_uuid}')
    if not redis_refresh_token or redis_refresh_token != refresh_token:
        invalid_message = await get_refresh_token_invalid_message(user_id, session_uuid)
        if not invalid_message:
            invalid_message = await get_token_invalid_message(user_id, session_uuid)
        raise errors.TokenError(msg=invalid_message or 'Refresh Token 已过期，请重新登录')

    await redis_client.delete(f'{settings.TOKEN_REFRESH_REDIS_PREFIX}:{user_id}:{session_uuid}')
    await redis_client.delete(f'{settings.TOKEN_REDIS_PREFIX}:{user_id}:{session_uuid}')

    new_access_token = await create_access_token(user_id, multi_login=True, **kwargs)
    new_refresh_token = await create_refresh_token(new_access_token.session_uuid, user_id, multi_login=multi_login)
    return NewToken(
        new_access_token=new_access_token.access_token,
        new_access_token_expire_time=new_access_token.access_token_expire_time,
        new_refresh_token=new_refresh_token.refresh_token,
        new_refresh_token_expire_time=new_refresh_token.refresh_token_expire_time,
        session_uuid=new_access_token.session_uuid,
    )


async def revoke_token(user_id: int, session_uuid: str) -> None:
    """
    撤销 token

    :param user_id: 用户 ID
    :param session_uuid: 会话 ID
    :return:
    """
    await redis_client.delete(f'{settings.TOKEN_REDIS_PREFIX}:{user_id}:{session_uuid}')
    await redis_client.delete(f'{settings.TOKEN_EXTRA_INFO_REDIS_PREFIX}:{user_id}:{session_uuid}')


def get_token(request: Request) -> str:
    """
    获取请求头中的 token

    :param request: FastAPI 请求对象
    :return:
    """
    authorization = request.headers.get('Authorization')
    scheme, token = get_authorization_scheme_param(authorization)
    if not authorization or scheme.lower() != 'bearer':
        raise errors.TokenError(msg='Token 无效')
    return token


async def get_current_user(db: AsyncSession, pk: int) -> User:
    """
    获取当前用户

    :param db: 数据库会话
    :param pk: 用户 ID
    :return:
    """
    from backend.app.admin.crud.crud_user import user_dao

    user = await user_dao.get_join(db, user_id=pk)
    if not user:
        raise errors.TokenError(msg='Token 无效')
    if not user.status:
        raise errors.AuthorizationError(msg='用户已被锁定，请联系系统管理员')
    if user.dept_id and not user.dept:
        raise errors.AuthorizationError(msg='用户所属部门不存在或已被删除，请联系系统管理员')
    if user.dept and not user.dept.status:
        raise errors.AuthorizationError(msg='用户所属部门已被锁定，请联系系统管理员')
    if user.roles:
        role_status = [role.status for role in user.roles]
        if all(status == 0 for status in role_status):
            raise errors.AuthorizationError(msg='用户所属角色已被锁定，请联系系统管理员')
    return user


async def get_jwt_user(user_id: int) -> GetUserInfoWithRelationDetail:
    """
    获取 JWT 用户

    :param user_id:
    :return:
    """
    cache_user = await redis_client.get(f'{settings.JWT_USER_REDIS_PREFIX}:{user_id}')
    if not cache_user:
        async with async_db_session() as db:
            current_user = await get_current_user(db, user_id)
            user = GetUserInfoWithRelationDetail.model_validate(current_user)
            await redis_client.set(
                f'{settings.JWT_USER_REDIS_PREFIX}:{user_id}',
                user.model_dump_json(),
                ex=settings.TOKEN_EXPIRE_SECONDS,
            )
    else:
        # TODO: 在恰当的时机，应替换为使用 model_validate_json
        # https://docs.pydantic.dev/latest/concepts/json/#partial-json-parsing
        user = GetUserInfoWithRelationDetail.model_validate(from_json(cache_user, allow_partial=True))
    return user


async def jwt_authentication(token: str) -> GetUserInfoWithRelationDetail:
    """
    JWT 认证

    :param token: JWT token
    :return:
    """
    token_payload = jwt_decode(token)
    ctx.user_id = token_payload.user_id

    redis_token = await redis_client.get(f'{settings.TOKEN_REDIS_PREFIX}:{ctx.user_id}:{token_payload.session_uuid}')
    if not redis_token:
        invalid_message = await get_token_invalid_message(ctx.user_id, token_payload.session_uuid)
        raise errors.TokenError(msg=invalid_message or 'Token 已过期')

    if token != redis_token:
        await mark_session_invalid(
            ctx.user_id, token_payload.session_uuid, reason=TokenInvalidReason.permission_changed
        )
        raise errors.TokenError(msg='Token 已失效')

    return await get_jwt_user(ctx.user_id)


def superuser_verify(request: Request, _token: str = DependsJwtAuth) -> bool:
    """
    验证当前用户超级管理员权限

    :param request: FastAPI 请求对象
    :param _token: JWT 令牌
    :return:
    """
    if isinstance(request.user, UnauthenticatedUser):
        raise errors.TokenError

    superuser = request.user.is_superuser
    if not superuser or not request.user.is_staff:
        raise errors.AuthorizationError
    return superuser


# 超级管理员鉴权依赖注入
DependsSuperUser = Depends(superuser_verify)
