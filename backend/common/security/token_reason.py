from enum import StrEnum
from typing import Any

from backend.core.conf import settings
from backend.database.redis import redis_client


class TokenInvalidReason(StrEnum):
    """会话主动失效原因（服务端记录，客户端不可刷新）"""

    session_replaced = 'session_replaced'
    logout = 'logout'
    password_changed = 'password_changed'
    admin_revoked = 'admin_revoked'
    policy_changed = 'policy_changed'
    account_deleted = 'account_deleted'


class TokenAuthReason(StrEnum):
    """认证失败原因（机器可读，随 401 响应返回）"""

    access_expired = 'access_expired'
    refresh_expired = 'refresh_expired'
    token_invalid = 'token_invalid'
    token_replaced = 'token_replaced'


TOKEN_AUTH_REASON_MESSAGES: dict[str, str] = {
    TokenInvalidReason.session_replaced.value: '账号已在其他设备登录，请重新登录',
    TokenInvalidReason.logout.value: '登录状态已失效，请重新登录',
    TokenInvalidReason.password_changed.value: '密码已变更，请重新登录',
    TokenInvalidReason.admin_revoked.value: '登录状态已被管理员撤销，请重新登录',
    TokenInvalidReason.policy_changed.value: '登录策略已变更，请重新登录',
    TokenInvalidReason.account_deleted.value: '账号已被删除，请重新登录',
    TokenAuthReason.access_expired.value: 'Token 已过期',
    TokenAuthReason.refresh_expired.value: 'Refresh Token 已过期，请重新登录',
    TokenAuthReason.token_invalid.value: 'Token 无效',
    TokenAuthReason.token_replaced.value: 'Token 已失效',
}

REFRESHABLE_AUTH_REASONS: frozenset[str] = frozenset({
    TokenAuthReason.access_expired.value,
    TokenAuthReason.token_replaced.value,
})


def auth_reason_message(reason: str, *, default: str = '登录状态已失效，请重新登录') -> str:
    """
    获取认证原因对应的提示文案

    :param reason: 认证原因
    :param default: 兜底文案
    :return:
    """
    return TOKEN_AUTH_REASON_MESSAGES.get(reason, default)


def auth_reason_data(reason: str) -> dict[str, Any]:
    """
    构造认证错误的机器可读数据

    :param reason: 认证原因
    :return:
    """
    return {'auth_reason': reason, 'refreshable': reason in REFRESHABLE_AUTH_REASONS}


def token_reason_key(user_id: int, session_uuid: str) -> str:
    """
    构造会话失效原因 key

    :param user_id: 用户 ID
    :param session_uuid: 会话 UUID
    :return:
    """
    return f'{settings.TOKEN_INVALID_REASON_REDIS_PREFIX}:{user_id}:{session_uuid}'


async def get_token_invalid_reason(user_id: int, session_uuid: str) -> str | None:
    """
    读取会话主动失效原因

    :param user_id: 用户 ID
    :param session_uuid: 会话 UUID
    :return:
    """
    return await redis_client.get(token_reason_key(user_id, session_uuid))


async def remember_token_invalid_reason(
    user_id: int,
    session_uuid: str,
    reason: TokenInvalidReason,
    *,
    ttl: int | None = None,
) -> None:
    """
    记录会话失效原因，TTL 覆盖整个 refresh token 生命周期

    :param user_id: 用户 ID
    :param session_uuid: 会话 UUID
    :param reason: 失效原因
    :param ttl: 自定义 TTL（秒），默认使用 refresh token 生命周期
    :return:
    """
    expire = ttl if ttl and ttl > 0 else settings.TOKEN_REFRESH_EXPIRE_SECONDS
    await redis_client.set(token_reason_key(user_id, session_uuid), reason.value, ex=expire)
