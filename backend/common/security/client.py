from datetime import datetime
from enum import StrEnum

from fastapi import Request, Response

from backend.common.context import ctx
from backend.common.exception import errors
from backend.core.conf import settings
from backend.utils.timezone import timezone


class LoginClientType(StrEnum):
    """站内客户端类型；浏览器、操作系统和登录方式不增加会话名额。"""

    admin = 'admin'
    web = 'web'
    miniapp = 'miniapp'
    extension = 'extension'


def get_login_client_type(request: Request | None = None) -> LoginClientType:
    """读取固定白名单内的客户端标识；未升级的密码登录客户端归入网页端。"""
    value = request.headers.get('X-Client-Type') if request is not None else ctx.client_type
    try:
        return LoginClientType(value or LoginClientType.web)
    except ValueError as exc:
        raise errors.RequestError(msg='不支持的登录客户端类型') from exc


def refresh_cookie_key(client_type: LoginClientType | str) -> str:
    """各端独立的刷新 Cookie，避免同域名下互相覆盖。"""
    return f'{settings.COOKIE_REFRESH_TOKEN_KEY}_{LoginClientType(client_type).value}'


def set_refresh_cookie(
    response: Response, client_type: LoginClientType, token: str, expire_time: datetime
) -> None:
    """只写入当前端的刷新凭据。"""
    response.set_cookie(
        key=refresh_cookie_key(client_type),
        value=token,
        max_age=settings.COOKIE_REFRESH_TOKEN_EXPIRE_SECONDS,
        expires=timezone.to_utc(expire_time),
        httponly=True,
    )
