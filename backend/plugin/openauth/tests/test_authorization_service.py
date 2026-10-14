"""完全隔离真实 DB/Redis 的授权协议、安全边界及并发回归测试。"""

# Test doubles intentionally accept lightweight objects in place of ORM sessions.
# ruff: noqa: ANN001, ANN201, ANN202, ANN204, RUF029
import asyncio
import importlib

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from jose import jwt
from pydantic import ValidationError

from backend.common.exception import errors
from backend.common.security.jwt import jwt_decode
from backend.core.conf import settings
from backend.plugin.openauth.dependencies import RequireOpenAuth
from backend.plugin.openauth.schema.authorization import (
    CreateOpenAuthAuthorizationParam,
    CreateOpenAuthRefreshParam,
    CreateOpenAuthRevokeParam,
    CreateOpenAuthTokenParam,
)
from backend.plugin.openauth.schema.client import CreateOpenAuthClientParam
from backend.plugin.openauth.service import constants as keys
from backend.plugin.openauth.service.authorization_service import OpenAuthAuthorizationService as Service
from backend.utils.timezone import timezone

auth_module = importlib.import_module('backend.plugin.openauth.service.authorization_service')
VERIFIER = 'a' * 64
SECRET = 'random-client-secret-for-testing-1234567890'


class FakeRedis:
    def __init__(self):
        self.store = {}
        self.ttls = {}

    async def set(self, key, value, ex=None):
        self.store[key] = value
        self.ttls[key] = ex

    async def get(self, key):
        value = self.store.get(key)
        # 让并发测试中的两个请求都读到旧值，以真正检验 GETDEL。
        await asyncio.sleep(0)
        return value

    async def getdel(self, key):
        return self.store.pop(key, None)

    async def delete(self, *names):
        for name in names:
            self.store.pop(name, None)

    async def expire(self, key, seconds):
        if key not in self.store:
            return False
        self.ttls[key] = seconds
        return True


@pytest.fixture
def env(monkeypatch):
    client = SimpleNamespace(
        id=1,
        client_id='oac_test',
        client_type='public',
        client_secret_hash=keys.hash_client_secret(SECRET),
        name='测试 Skill',
        description=None,
        icon=None,
        scopes=['profile:read', 'practice:read'],
        redirect_uris=['http://127.0.0.1:17888/callback'],
        status=1,
        deleted=0,
    )
    grant = SimpleNamespace(
        id=11,
        user_id=100,
        client_id=1,
        scopes=['profile:read'],
        status='active',
        grant_version='test-grant-version',
        last_used_time=None,
        authorized_time=timezone.now(),
        created_time=timezone.now(),
    )
    redis = FakeRedis()
    monkeypatch.setattr(auth_module, 'redis_client', redis)

    async def lookup(db, *, client_id):
        if client_id != client.client_id:
            raise errors.NotFoundError
        if client.status != 1 or client.deleted:
            raise errors.ForbiddenError
        return client

    async def active(db, *, user_id, client_pk):
        return grant if grant.status == 'active' else None

    async def upsert(db, *, user_id, client_pk, obj):
        if grant.status != 'active':
            grant.grant_version = keys.generate_code()
        grant.status = 'active'
        grant.scopes = obj.scopes
        return grant

    async def revoke(db, *, user_id, client_pk):
        grant.status = 'revoked'
        grant.grant_version = keys.generate_code()

    monkeypatch.setattr(auth_module.openauth_client_service, 'get_enabled_by_client_id', lookup)
    dao = auth_module.openauth_user_authorization_dao
    monkeypatch.setattr(dao, 'get_active_by_user_and_client', active)
    monkeypatch.setattr(dao, 'upsert_authorization', upsert)
    monkeypatch.setattr(dao, 'revoke', revoke)
    monkeypatch.setattr(dao, 'touch_last_used', AsyncMock())
    monkeypatch.setattr(auth_module, 'get_current_user', AsyncMock(return_value=SimpleNamespace(id=100)))
    return SimpleNamespace(client=client, grant=grant, redis=redis)


def authorize_param(env, **overrides):
    return CreateOpenAuthAuthorizationParam(**{
        'client_id': env.client.client_id,
        'scopes': ['profile:read'],
        'redirect_uri': env.client.redirect_uris[0],
        'state': 'random-csrf-state-1234567890',
        'code_challenge': keys.pkce_challenge(VERIFIER),
        **overrides,
    })


async def new_code(env):
    return await Service.authorize(None, user_id=100, client=env.client, obj=authorize_param(env))


def token_param(env, code, **overrides):
    return CreateOpenAuthTokenParam(**{
        'client_id': env.client.client_id,
        'code': code,
        'redirect_uri': env.client.redirect_uris[0],
        'code_verifier': VERIFIER,
        'client_secret': SECRET if env.client.client_type == 'confidential' else None,
        **overrides,
    })


async def login(env):
    code = await new_code(env)
    return await Service.create_token(None, obj=token_param(env, code.code))


def refresh_param(env, token, **overrides):
    return CreateOpenAuthRefreshParam(**{
        'client_id': env.client.client_id,
        'refresh_token': token,
        'client_secret': SECRET if env.client.client_type == 'confidential' else None,
        **overrides,
    })


def test_pkce_rfc7636_vector():
    assert keys.pkce_challenge('dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk') == (
        'E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM'
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('client_type', ['public', 'confidential'])
async def test_complete_flow(env, client_type):
    env.client.client_type = client_type
    tokens = await login(env)
    identity = await Service.check(None, token=tokens.access_token)
    assert (identity.user_id, identity.scopes, identity.authorized) == (100, ['profile:read'], True)
    refreshed = await Service.refresh(None, obj=refresh_param(env, tokens.refresh_token))
    assert refreshed.access_token != tokens.access_token
    assert refreshed.refresh_token != tokens.refresh_token
    assert keys.refresh_token_key(tokens.refresh_token) not in env.redis.store
    assert env.redis.ttls[keys.access_token_key(refreshed.access_token)] == 7200
    assert env.redis.ttls[keys.refresh_token_key(refreshed.refresh_token)] == 2592000


@pytest.mark.asyncio
async def test_new_scopes_require_confirmation(env):
    preview = await Service.get_authorize_preview(None, user_id=100, client=env.client, obj=authorize_param(env))
    assert preview.already_authorized
    preview = await Service.get_authorize_preview(
        None,
        user_id=100,
        client=env.client,
        obj=authorize_param(env, scopes=['practice:read']),
    )
    assert not preview.already_authorized


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'overrides',
    [
        {'scopes': ['admin:write']},
        {'redirect_uri': 'https://evil.example/callback'},
    ],
)
async def test_invalid_authorize_request(env, overrides):
    with pytest.raises(errors.ForbiddenError):
        await Service.authorize(None, user_id=100, client=env.client, obj=authorize_param(env, **overrides))
    assert not env.redis.store


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'overrides',
    [
        {'code_verifier': 'b' * 64},
        {'redirect_uri': 'http://127.0.0.1:19999/callback'},
        {'client_secret': 'wrong'},
    ],
)
async def test_invalid_exchange_does_not_burn_code(env, overrides):
    env.client.client_type = 'confidential'
    code = await new_code(env)
    with pytest.raises(errors.ForbiddenError):
        await Service.create_token(None, obj=token_param(env, code.code, **overrides))
    assert keys.code_key(code.code) in env.redis.store


@pytest.mark.asyncio
async def test_code_is_atomic_and_single_use(env):
    code = await new_code(env)
    param = token_param(env, code.code)
    outcomes = await asyncio.gather(
        Service.create_token(None, obj=param),
        Service.create_token(None, obj=param),
        return_exceptions=True,
    )
    assert sum(isinstance(outcome, errors.TokenError) for outcome in outcomes) == 1
    assert sum(not isinstance(outcome, Exception) for outcome in outcomes) == 1


@pytest.mark.asyncio
async def test_refresh_is_atomic_and_single_use(env):
    tokens = await login(env)
    param = refresh_param(env, tokens.refresh_token)
    outcomes = await asyncio.gather(
        Service.refresh(None, obj=param), Service.refresh(None, obj=param), return_exceptions=True
    )
    assert sum(isinstance(outcome, errors.TokenError) for outcome in outcomes) == 1
    assert sum(not isinstance(outcome, Exception) for outcome in outcomes) == 1


@pytest.mark.asyncio
async def test_refresh_never_gains_later_scopes(env):
    tokens = await login(env)
    env.grant.scopes.append('practice:read')
    result = await Service.refresh(None, obj=refresh_param(env, tokens.refresh_token))
    assert (await Service.check(None, token=result.access_token)).scopes == ['profile:read']


@pytest.mark.asyncio
async def test_scope_reduction_is_enforced_at_resource(env):
    tokens = await login(env)
    env.client.scopes = ['practice:read']
    assert (await Service.check(None, token=tokens.access_token)).scopes == []
    with pytest.raises(errors.ForbiddenError):
        await RequireOpenAuth('profile:read')(None, tokens.access_token)
    with pytest.raises(errors.ForbiddenError):
        await Service.refresh(None, obj=refresh_param(env, tokens.refresh_token))


@pytest.mark.asyncio
@pytest.mark.parametrize('operation', ['exchange', 'check', 'refresh'])
async def test_disabled_clients_cannot_use_credentials(env, operation):
    tokens = await login(env)
    code = await new_code(env)
    env.client.status = 0
    with pytest.raises(errors.ForbiddenError):
        if operation == 'exchange':
            await Service.create_token(None, obj=token_param(env, code.code))
        elif operation == 'check':
            await Service.check(None, token=tokens.access_token)
        else:
            await Service.refresh(None, obj=refresh_param(env, tokens.refresh_token))


@pytest.mark.asyncio
async def test_disabled_user_cannot_use_token(env, monkeypatch):
    tokens = await login(env)
    monkeypatch.setattr(auth_module, 'get_current_user', AsyncMock(side_effect=errors.AuthorizationError()))
    with pytest.raises(errors.AuthorizationError):
        await Service.check(None, token=tokens.access_token)


@pytest.mark.asyncio
async def test_confidential_refresh_requires_secret(env):
    env.client.client_type = 'confidential'
    tokens = await login(env)
    with pytest.raises(errors.ForbiddenError):
        await Service.refresh(None, obj=refresh_param(env, tokens.refresh_token, client_secret=None))
    assert keys.refresh_token_key(tokens.refresh_token) in env.redis.store


@pytest.mark.asyncio
async def test_revoke_and_reauthorize_never_revives_old_credentials(env):
    tokens = await login(env)
    old_code = await new_code(env)
    await Service.revoke(
        None, user_id=100, client=env.client, obj=CreateOpenAuthRevokeParam(client_id=env.client.client_id)
    )
    for reauthorized in (False, True):
        if reauthorized:
            fresh = await login(env)
            assert (await Service.check(None, token=fresh.access_token)).authorized
        with pytest.raises(errors.TokenError):
            await Service.check(None, token=tokens.access_token)
        with pytest.raises(errors.TokenError):
            await Service.refresh(None, obj=refresh_param(env, tokens.refresh_token))
        with pytest.raises(errors.TokenError):
            await Service.create_token(None, obj=token_param(env, old_code.code))


@pytest.mark.asyncio
async def test_logout_only_affects_one_device(env):
    first, second = await login(env), await login(env)
    await Service.logout(None, token=first.access_token)
    with pytest.raises(errors.TokenError):
        await Service.check(None, token=first.access_token)
    with pytest.raises(errors.TokenError):
        await Service.refresh(None, obj=refresh_param(env, first.refresh_token))
    assert (await Service.check(None, token=second.access_token)).authorized
    assert env.grant.status == 'active'


@pytest.mark.asyncio
async def test_logout_cannot_be_undone_by_concurrent_refresh(env):
    tokens = await login(env)
    payload = auth_module._decode_openauth_token(tokens.access_token)
    await Service.logout(None, token=tokens.access_token)
    with pytest.raises(errors.TokenError):
        await Service._issue_tokens(
            user_id=100,
            client=env.client,
            scopes=['profile:read'],
            grant_version=env.grant.grant_version,
            session_id=payload['sid'],
        )


@pytest.mark.asyncio
async def test_token_domain_separation_and_required_claims(env):
    tokens = await login(env)
    with pytest.raises(errors.TokenError):
        jwt_decode(tokens.access_token)
    payload = auth_module._decode_openauth_token(tokens.access_token)
    for mutation in ({'aud': 'other'}, {'iss': 'other'}, {'exp': 1}, {'scopes': 'profile:read'}, {'sid': None}):
        bad = jwt.encode({**payload, **mutation}, settings.TOKEN_SECRET_KEY, algorithm=settings.TOKEN_ALGORITHM)
        with pytest.raises(errors.TokenError):
            await Service.check(None, token=bad)


@pytest.mark.asyncio
async def test_tokens_same_second_are_unique_and_redis_keys_are_hashed(env):
    first, second = await login(env), await login(env)
    assert first.access_token != second.access_token
    assert first.access_token not in keys.access_token_key(first.access_token)
    assert first.refresh_token not in keys.refresh_token_key(first.refresh_token)


@pytest.mark.parametrize(
    'uri', ['https://app.example/callback', 'http://127.0.0.1:17888/callback', 'http://[::1]:8080/cb']
)
def test_valid_redirect_registration(uri):
    assert CreateOpenAuthClientParam(name='CLI', client_type='public', redirect_uris=[uri]).redirect_uris == [uri]


@pytest.mark.parametrize(
    'uri',
    [
        'http://evil.example/callback',
        'javascript:alert(1)',
        'https://app.example/*',
        'https://user:pass@app.example/cb',
        'https://app.example/cb#fragment',
        'http://127.0.0.1:99999/cb',
        'https://app.example\\evil/cb',
    ],
)
def test_invalid_redirect_registration(uri):
    with pytest.raises(ValidationError):
        CreateOpenAuthClientParam(name='CLI', redirect_uris=[uri])


def test_public_client_has_no_secret():
    with pytest.raises(ValidationError):
        CreateOpenAuthClientParam(name='CLI', client_type='public', client_secret=SECRET)
