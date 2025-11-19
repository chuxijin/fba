#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
统一认证中间件

支持多种用户类型的可扩展认证中间件
"""
from typing import Any

from fastapi import Request, Response
from fastapi.security.utils import get_authorization_scheme_param
from starlette.authentication import AuthCredentials, AuthenticationBackend, AuthenticationError
from starlette.requests import HTTPConnection

from backend.common.exception.errors import TokenError
from backend.common.log import log
from backend.common.security.unified_token import verify_unified_token
from backend.core.conf import settings
from backend.utils.serializers import MsgSpecJSONResponse


class _UnifiedAuthenticationError(AuthenticationError):
    """统一认证错误类"""

    def __init__(
        self,
        *,
        code: int | None = None,
        msg: str | None = None,
        headers: dict[str, Any] | None = None,
    ) -> None:
        """
        初始化认证错误

        :param code: 错误码
        :param msg: 错误信息
        :param headers: 响应头
        :return:
        """
        self.code = code
        self.msg = msg
        self.headers = headers


class UnifiedAuthMiddleware(AuthenticationBackend):
    """统一认证中间件"""

    @staticmethod
    def auth_exception_handler(conn: HTTPConnection, exc: _UnifiedAuthenticationError) -> Response:
        """
        认证错误处理

        :param conn: HTTP 连接对象
        :param exc: 认证错误对象
        :return:
        """
        status_code = exc.code if isinstance(exc.code, int) else 500
        return MsgSpecJSONResponse(content={'code': exc.code, 'msg': exc.msg, 'data': None}, status_code=status_code)

    async def authenticate(self, request: Request) -> tuple[AuthCredentials, Any] | None:
        """
        认证请求

        :param request: FastAPI 请求对象
        :return:
        """
        token = request.headers.get('Authorization')
        if not token:
            return None

        # 检查白名单
        path = request.url.path
        if path in settings.TOKEN_REQUEST_PATH_EXCLUDE:
            return None
        for pattern in settings.TOKEN_REQUEST_PATH_EXCLUDE_PATTERN:
            if pattern.match(path):
                return None

        # 提取 Bearer token
        scheme, token = get_authorization_scheme_param(token)
        if scheme.lower() != 'bearer':
            return None

        # 尝试统一验证（新格式 token）
        try:
            user = await verify_unified_token(token)

            # 将用户信息附加到 request.state
            request.state.auth_user = user

            return AuthCredentials(['authenticated', user.user_type]), user

        except TokenError as exc:
            # 如果错误信息包含 "缺少 user_type"，说明可能是旧格式 admin token
            if '缺少 user_type' in exc.detail or 'user_type' in exc.detail:
                # 尝试旧格式验证
                pass
            else:
                # 其他错误（过期、无效等）直接抛出
                raise _UnifiedAuthenticationError(
                    code=exc.status_code, msg=exc.detail, headers=getattr(exc, 'headers', None)
                )
        except Exception:
            # 其他异常，尝试旧格式
            pass

        # 回退到旧的 Admin token 验证（向后兼容）
        try:
            from backend.common.security.jwt import jwt_authentication

            user = await jwt_authentication(token)

            # 兼容旧的 Admin 认证返回格式
            return AuthCredentials(['authenticated', 'admin']), user

        except TokenError as exc:
            raise _UnifiedAuthenticationError(
                code=exc.status_code, msg=exc.detail, headers=getattr(exc, 'headers', None)
            )
        except Exception as e:
            log.exception(f'认证异常：{e}')
            raise _UnifiedAuthenticationError(code=getattr(e, 'code', 500), msg=getattr(e, 'msg', '认证失败'))
