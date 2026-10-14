# ruff: noqa: ANN001, ANN201, ANN202, RUF029
import importlib

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette_context.middleware import RawContextMiddleware

from backend.common.exception import errors
from backend.core.conf import settings
from backend.database.db import get_db_transaction
from backend.middleware.jwt_auth_middleware import JwtAuthMiddleware
from backend.plugin.openauth.api.router import v1
from backend.plugin.openauth.hooks import setup
from backend.plugin.openauth.schema.authorization import GetOpenAuthCheckResult
from backend.plugin.openauth.service.profile_service import openauth_profile_service
from backend.utils.timezone import timezone

auth = importlib.import_module('backend.plugin.openauth.service.authorization_service')
profile = importlib.import_module('backend.plugin.openauth.service.profile_service')


def test_profile_enforces_scope_and_ignores_other_user_id(monkeypatch):
    app = FastAPI()
    app.include_router(v1)
    monkeypatch.setattr(settings, 'TOKEN_REQUEST_PATH_EXCLUDE', list(settings.TOKEN_REQUEST_PATH_EXCLUDE))
    monkeypatch.setattr(settings, 'OPERA_LOG_REDACT_KEYS', list(settings.OPERA_LOG_REDACT_KEYS))
    setup(app)
    app.add_middleware(AuthenticationMiddleware, backend=JwtAuthMiddleware())
    app.add_middleware(RawContextMiddleware)

    async def db():
        yield None

    @app.exception_handler(errors.BaseExceptionError)
    async def error_handler(request, exc):
        return JSONResponse(status_code=exc.code, content={'msg': exc.msg})

    app.dependency_overrides[get_db_transaction] = db
    identity = GetOpenAuthCheckResult(
        user_id=123,
        client_id='test',
        scopes=['profile:read'],
        authorized=True,
        expires_at=timezone.now(),
    )
    monkeypatch.setattr(auth.openauth_authorization_service, 'check', AsyncMock(return_value=identity))
    get_user = AsyncMock(
        return_value=SimpleNamespace(id=123, nickname='测试用户', avatar=None, email='private@example.com')
    )
    monkeypatch.setattr(profile, 'get_current_user', get_user)
    with TestClient(app) as client:
        url = f'{settings.FASTAPI_API_V1_PATH}/openauth/profile?user_id=999'
        assert client.get(url).status_code == 401
        result = client.get(url, headers={'Authorization': 'Bearer third-party'})
        assert result.status_code == 200
        assert result.json()['data'] == {
            'user_id': 123,
            'nickname': '测试用户',
            'avatar': None,
            'can_use_skill': False,
            'skill_deny_message': None,
        }
        assert get_user.call_args.args[1] == 123
        identity.scopes = []
        assert client.get(url, headers={'Authorization': 'Bearer third-party'}).status_code == 403


@pytest.mark.asyncio
async def test_profile_rechecks_user_status(monkeypatch):
    monkeypatch.setattr(profile, 'get_current_user', AsyncMock(side_effect=errors.AuthorizationError()))
    with pytest.raises(errors.AuthorizationError):
        await openauth_profile_service.get_profile(None, user_id=123)
