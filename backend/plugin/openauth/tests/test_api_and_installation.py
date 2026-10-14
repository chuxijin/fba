"""真实 FastAPI 路由/依赖 + 隔离的事务与服务桩，不连接开发或生产数据库。"""

# ruff: noqa: ANN001, ANN201, ANN202, RUF029
import importlib
import re

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import tomllib

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient
from sqlalchemy.dialects import postgresql
from starlette.authentication import AuthCredentials
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette_context.middleware import RawContextMiddleware

from backend.common.exception import errors
from backend.common.security.jwt import jwt_authentication_verify
from backend.core.conf import settings
from backend.database.db import get_db, get_db_transaction
from backend.middleware.jwt_auth_middleware import JwtAuthMiddleware
from backend.plugin.openauth.api.router import v1
from backend.plugin.openauth.crud.crud_openauth import CRUDOpenAuthUserAuthorization
from backend.plugin.openauth.hooks import setup
from backend.plugin.openauth.model import OpenAuthClient, OpenAuthUserAuthorization
from backend.plugin.openauth.schema.authorization import GetOpenAuthCheckResult
from backend.plugin.openauth.schema.client import CreateOpenAuthClientParam, GetOpenAuthClientDetail
from backend.plugin.openauth.service.client_service import openauth_client_service
from backend.plugin.openauth.tests.test_authorization_service import authorize_param
from backend.plugin.openauth.tests.test_authorization_service import env as authorization_env
from backend.plugin.validator import validate_plugin_config
from backend.utils.timezone import timezone

api = importlib.import_module('backend.plugin.openauth.api.v1.openauth')
PREFIX = f'{settings.FASTAPI_API_V1_PATH}/openauth'
env = authorization_env


@pytest.fixture
def http(monkeypatch):
    monkeypatch.setattr(settings, 'TOKEN_REQUEST_PATH_EXCLUDE', list(settings.TOKEN_REQUEST_PATH_EXCLUDE))
    monkeypatch.setattr(settings, 'OPERA_LOG_REDACT_KEYS', list(settings.OPERA_LOG_REDACT_KEYS))
    monkeypatch.setattr(settings, 'RBAC_ROLE_MENU_MODE', True)
    app = FastAPI()
    app.include_router(v1)
    setup(app)
    app.add_middleware(
        AuthenticationMiddleware, backend=JwtAuthMiddleware(), on_error=JwtAuthMiddleware.auth_exception_handler
    )
    app.add_middleware(RawContextMiddleware)
    state = SimpleNamespace(commits=0, rollbacks=0, user_id=100, perms=set())

    async def read_session():
        yield None

    async def transaction():
        try:
            yield None
        except Exception:
            state.rollbacks += 1
            raise
        else:
            state.commits += 1

    def user(request: Request):
        request.scope['user'] = SimpleNamespace(
            id=state.user_id,
            is_staff=True,
            is_superuser=False,
            roles=[SimpleNamespace(status=1, menus=[SimpleNamespace(id=1, status=1, perms=','.join(state.perms))])],
        )
        request.scope['auth'] = AuthCredentials(['authenticated'])
        return 'test-site-login'

    @app.exception_handler(errors.BaseExceptionError)
    async def domain_error(request: Request, exc):
        return JSONResponse(status_code=exc.code, content={'code': exc.code, 'msg': exc.msg})

    app.dependency_overrides[get_db] = read_session
    app.dependency_overrides[get_db_transaction] = transaction
    app.dependency_overrides[jwt_authentication_verify] = user
    with TestClient(app) as client:
        yield client, state


def test_authorize_uses_transaction_and_current_user(http, env, monkeypatch):
    client, state = http
    service = AsyncMock(
        return_value=SimpleNamespace(
            code='authorization-code',
            redirect_uri=env.client.redirect_uris[0],
            state='random-csrf-state-1234567890',
            expires_in=300,
        )
    )
    # 返回真实 Schema，让响应序列化也参与验证。
    from backend.plugin.openauth.schema.authorization import GetOpenAuthAuthorizationResult

    service.return_value = GetOpenAuthAuthorizationResult(**vars(service.return_value))
    monkeypatch.setattr(api.openauth_authorization_service, 'authorize', service)
    result = client.post(f'{PREFIX}/authorize', json=authorize_param(env).model_dump())
    assert result.status_code == 200
    assert state.commits == 1
    assert service.call_args.kwargs['user_id'] == 100
    assert result.headers['cache-control'] == 'no-store'


def test_authorization_failure_rolls_back(http, env, monkeypatch):
    client, state = http
    monkeypatch.setattr(api.openauth_authorization_service, 'authorize', AsyncMock(side_effect=errors.ForbiddenError()))
    result = client.post(f'{PREFIX}/authorize', json=authorize_param(env).model_dump())
    assert result.status_code == 403
    assert state.commits == 0 and state.rollbacks == 1


def test_check_requires_header_and_bypasses_only_site_jwt(http, monkeypatch):
    client, state = http
    check = AsyncMock(
        return_value=GetOpenAuthCheckResult(
            user_id=100,
            client_id='oac_test',
            scopes=['profile:read'],
            authorized=True,
            expires_at=timezone.now(),
        )
    )
    monkeypatch.setattr(api.openauth_authorization_service, 'check', check)
    assert client.post(f'{PREFIX}/check?token=do-not-accept-query-token').status_code == 401
    result = client.post(f'{PREFIX}/check', headers={'Authorization': 'Bearer openauth-token'})
    assert result.status_code == 200
    assert check.call_args.kwargs['token'] == 'openauth-token'
    assert state.commits == 1
    assert f'{PREFIX}/authorize' not in settings.TOKEN_REQUEST_PATH_EXCLUDE
    assert f'{PREFIX}/clients' not in settings.TOKEN_REQUEST_PATH_EXCLUDE


@pytest.mark.parametrize(
    'suffix,method,permission,body,service',
    [
        ('/clients', 'post', 'openauth:client:add', {'name': 'CLI', 'client_type': 'public'}, 'create'),
        ('/clients/1', 'put', 'openauth:client:edit', {'name': 'CLI'}, 'update'),
        ('/clients/1', 'delete', 'openauth:client:delete', None, 'delete'),
        ('/clients/1/secret', 'put', 'openauth:client:secret', {}, 'reset_secret'),
        ('/clients/1', 'get', 'openauth:client:view', None, 'get'),
        ('/clients', 'get', 'openauth:client:list', None, 'get_page'),
    ],
)
def test_client_management_requires_specific_permission(http, monkeypatch, suffix, method, permission, body, service):
    client, state = http
    operation = AsyncMock(side_effect=errors.ConflictError(msg='service-reached'))
    monkeypatch.setattr(api.openauth_client_service, service, operation)
    assert client.request(method, f'{PREFIX}{suffix}', json=body).status_code == 403
    operation.assert_not_called()
    state.perms.add(permission)
    assert client.request(method, f'{PREFIX}{suffix}', json=body).status_code == 409
    operation.assert_called_once()


def test_secret_is_in_body_not_url_and_redacted(http):
    client, _ = http
    path = client.app.openapi()['paths'][f'{PREFIX}/clients/{{pk}}/secret']['put']
    assert 'requestBody' in path
    assert not any(p['name'] == 'new_secret' for p in path.get('parameters', []))
    assert {'client_secret', 'new_secret', 'code_verifier', 'refresh_token'} <= set(settings.OPERA_LOG_REDACT_KEYS)


def test_authorization_listing_cannot_select_other_user(http, monkeypatch):
    client, _ = http
    operation = AsyncMock(return_value=[])
    monkeypatch.setattr(api.openauth_authorization_service, 'list_authorizations', operation)
    assert client.get(f'{PREFIX}/authorizations?user_id=999').status_code == 200
    assert operation.call_args.kwargs['user_id'] == 100


@pytest.mark.asyncio
async def test_create_public_and_confidential_clients():
    class Session:
        def add(self, row):
            row.id = 123

        async def flush(self):
            pass

    for client_type in ('public', 'confidential'):
        result = await openauth_client_service.create(
            Session(), obj=CreateOpenAuthClientParam(name='CLI', client_type=client_type)
        )
        assert (result.client_secret is None) == (client_type == 'public')
        assert 'client_secret_hash' not in result.model_dump()


@pytest.mark.asyncio
async def test_upsert_is_atomic_and_bound_to_correct_constraint(env):
    captured = {}

    class Session:
        async def execute(self, stmt):
            captured['sql'] = str(stmt.compile(dialect=postgresql.dialect()))
            return SimpleNamespace(scalar_one=lambda: env.grant)

    result = await CRUDOpenAuthUserAuthorization(OpenAuthUserAuthorization).upsert_authorization(
        Session(),
        user_id=100,
        client_pk=1,
        obj=authorize_param(env),
    )
    assert result is env.grant
    assert 'ON CONFLICT ON CONSTRAINT uk_openauth_user_auth_user_client DO UPDATE' in captured['sql']
    assert 'grant_version = CASE' in captured['sql']


def test_install_sql_matches_models_and_never_touches_legacy_tables():
    root = Path(__file__).resolve().parents[1]
    config = tomllib.loads((root / 'plugin.toml').read_text(encoding='utf-8'))
    validate_plugin_config('openauth', config)
    for suffix in ('', '_snowflake'):
        sql = (root / 'sql' / 'postgresql' / f'init{suffix}.sql').read_text(encoding='utf-8')
        assert 'skill_' not in sql
        for model in (OpenAuthClient, OpenAuthUserAuthorization):
            table_body = re.search(rf'CREATE TABLE {model.__tablename__} \((.*?)\n\);', sql, re.DOTALL).group(1)
            for column in model.__table__.columns:
                assert re.search(rf'^\s+{column.name}\s', table_body, re.MULTILINE), column.name
        destroy = (root / 'sql' / 'postgresql' / f'destroy{suffix}.sql').read_text(encoding='utf-8')
        assert 'skill_' not in destroy
    assert (root / 'sql/postgresql/init_snowflake.sql').read_text(encoding='utf-8').count('bigserial') == 0


def test_client_detail_never_exposes_secret_hash():
    row = OpenAuthClient(client_id='oac_test', client_secret_hash='secret-hash', name='CLI')
    row.id = 1
    assert 'client_secret_hash' not in GetOpenAuthClientDetail.model_validate(row).model_dump()
