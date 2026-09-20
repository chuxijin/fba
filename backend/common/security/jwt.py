from typing import Annotated, Any

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import ExpiredSignatureError, JWTError, jwt
from pydantic_core import from_json
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.authentication import UnauthenticatedUser

from backend.app.admin.model import User
from backend.app.admin.schema.user import GetUserInfoWithRelationDetail
from backend.common.context import ctx
from backend.common.dataclasses import TokenPayload
from backend.common.exception import errors
from backend.common.security.token_reason import (
    TokenAuthReason,
    auth_reason_data,
    auth_reason_message,
    get_token_invalid_reason,
)
from backend.core.conf import settings
from backend.database.db import async_db_session
from backend.database.redis import redis_client
from backend.utils.timezone import timezone


def jwt_encode(payload: dict[str, Any]) -> str:
    """
    生成 JWT token

    :param payload: 载荷
    :return:
    """
    return jwt.encode(payload, settings.TOKEN_SECRET_KEY, settings.TOKEN_ALGORITHM)


def jwt_decode(token: str, *, verify_exp: bool = True) -> TokenPayload:
    """
    解析 JWT token

    :param token: JWT token
    :param verify_exp: 是否校验过期时间；关闭后可用于识别已过期 token 的失效原因
    :return:
    """
    try:
        payload = jwt.decode(
            token,
            settings.TOKEN_SECRET_KEY,
            algorithms=[settings.TOKEN_ALGORITHM],
            options={'verify_exp': verify_exp},
        )
        session_uuid = payload.get('session_uuid')
        user_id = payload.get('sub')
        expire = payload.get('exp')
        if not session_uuid or not user_id or not expire:
            raise errors.TokenError(
                msg=auth_reason_message(TokenAuthReason.token_invalid.value),
                data=auth_reason_data(TokenAuthReason.token_invalid.value),
            )
    except errors.TokenError:
        raise
    except ExpiredSignatureError:
        raise errors.TokenError(
            msg=auth_reason_message(TokenAuthReason.access_expired.value),
            data=auth_reason_data(TokenAuthReason.access_expired.value),
        )
    except (JWTError, Exception):
        raise errors.TokenError(
            msg=auth_reason_message(TokenAuthReason.token_invalid.value),
            data=auth_reason_data(TokenAuthReason.token_invalid.value),
        )
    return TokenPayload(
        user_id=int(user_id),
        session_uuid=session_uuid,
        expire_time=timezone.from_datetime(timezone.to_utc(expire)),
    )


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

    :param user_id: 用户 ID
    :return:
    """
    user_key = f'{settings.JWT_USER_REDIS_PREFIX}:{user_id}'
    cache_user = await redis_client.get(user_key)
    if not cache_user:
        async with async_db_session() as db:
            current_user = await get_current_user(db, user_id)
            user = GetUserInfoWithRelationDetail.model_validate(current_user)
            await redis_client.set(
                user_key,
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
    # 先不校验过期，优先识别服务端记录的主动失效原因
    token_payload = jwt_decode(token, verify_exp=False)
    ctx.user_id = token_payload.user_id

    invalid_reason = await get_token_invalid_reason(token_payload.user_id, token_payload.session_uuid)
    if invalid_reason:
        raise errors.TokenError(
            msg=auth_reason_message(invalid_reason),
            data=auth_reason_data(invalid_reason),
        )

    if token_payload.expire_time <= timezone.now():
        raise errors.TokenError(
            msg=auth_reason_message(TokenAuthReason.access_expired.value),
            data=auth_reason_data(TokenAuthReason.access_expired.value),
        )

    redis_token = await redis_client.get(f'{settings.TOKEN_REDIS_PREFIX}:{ctx.user_id}:{token_payload.session_uuid}')
    if not redis_token:
        # 未被主动标记失效，仅说明 access token 已不在（自然过期）
        raise errors.TokenError(
            msg=auth_reason_message(TokenAuthReason.access_expired.value),
            data=auth_reason_data(TokenAuthReason.access_expired.value),
        )
    if token != redis_token:
        raise errors.TokenError(
            msg=auth_reason_message(TokenAuthReason.token_replaced.value),
            data=auth_reason_data(TokenAuthReason.token_replaced.value),
        )

    user = await get_jwt_user(ctx.user_id)
    ctx.is_superuser = user.is_superuser
    return user


def jwt_authentication_verify(
    request: Request,
    token: Annotated[HTTPAuthorizationCredentials, Depends(HTTPBearer())],
) -> str:
    """
    JWT 认证依赖

    :param request: FastAPI 请求对象
    :param token: HTTP Bearer 认证信息
    :return:
    """
    if isinstance(request.user, UnauthenticatedUser):
        if token_exception := ctx.get('__request_jwt_authentication_exception__'):
            raise token_exception
        raise errors.TokenError
    return token.credentials


# JWT 依赖注入
DependsJwtAuth = Depends(jwt_authentication_verify)


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
