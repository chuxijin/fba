from fastapi import FastAPI

from backend.core.conf import settings


def setup(app: FastAPI) -> None:
    """仅跳过独立 Bearer 接口的站内 JWT 中间件；接口仍强制执行 OpenAuth 鉴权。"""
    del app
    for suffix in ('check', 'logout', 'profile', 'unauthorize'):
        path = f'{settings.FASTAPI_API_V1_PATH}/openauth/{suffix}'
        if path not in settings.TOKEN_REQUEST_PATH_EXCLUDE:
            settings.TOKEN_REQUEST_PATH_EXCLUDE.append(path)
    for key in (
        'client_secret',
        'new_client_secret',
        'new_secret',
        'code',
        'code_verifier',
        'access_token',
        'refresh_token',
        'token',
        'ticket',
    ):
        if key not in settings.OPERA_LOG_REDACT_KEYS:
            settings.OPERA_LOG_REDACT_KEYS.append(key)
