import asyncio
import json

from collections import defaultdict
from datetime import timedelta
from types import SimpleNamespace
from typing import Any, Self
from unittest.mock import AsyncMock

import pytest

from fastapi import BackgroundTasks, Response
from fastapi.security import HTTPBasicCredentials
from starlette.requests import Request

from backend.app.admin.schema.token import GetLoginToken
from backend.app.admin.service import auth_service as auth_module
from backend.common.dataclasses import NewToken
from backend.common.exception import errors
from backend.common.security import jwt as jwt_module
from backend.common.security import token as tokens
from backend.common.security import token_reason
from backend.common.security.client import LoginClientType, get_login_client_type, refresh_cookie_key
from backend.core.conf import settings
from backend.plugin.oauth2.service import wechat_scan_service as scan_module
from backend.utils.timezone import timezone


class MemoryRedis:
    """保留异步调度及互斥语义，测试不连接或修改任何环境的 Redis/数据库。"""

    def __init__(self) -> None:
        self.values = {}
        self.sets = defaultdict(set)
        self.locks = defaultdict(asyncio.Lock)

    async def get(self, key: str) -> str | None:
        await asyncio.sleep(0)
        return self.values.get(key)

    async def set(self, key: str, value: str, **_kwargs: Any) -> bool:
        self.values[key] = value
        return True

    async def exists(self, key: str) -> int:
        return int(key in self.values or bool(self.sets.get(key)))

    async def getdel(self, key: str) -> str | None:
        return self.values.pop(key, None)

    async def delete(self, *keys: str) -> None:
        for key in keys:
            self.values.pop(key, None)
            self.sets.pop(key, None)

    async def delete_batched(self, keys: list[str]) -> None:
        await self.delete(*keys)

    async def smembers(self, key: str) -> set[str]:
        return set(self.sets[key])

    async def sadd(self, key: str, *values: str) -> None:
        self.sets[key].update(values)

    async def srem(self, key: str, *values: str) -> None:
        self.sets[key].difference_update(values)

    async def expire(self, key: str, _seconds: int) -> int:
        return await self.exists(key)

    async def mget_batched(self, keys: list[str]) -> list[str | None]:
        return [await self.get(key) for key in keys]

    async def smembers_many(self, keys: list[str]) -> list[set[str]]:
        return [await self.smembers(key) for key in keys]

    def lock(self, key: str, **_kwargs: Any) -> asyncio.Lock:
        return self.locks[key]

    def pipeline(self, **_kwargs: Any) -> Any:
        redis = self

        class Pipeline:
            def __init__(self) -> None:
                self.calls = []

            async def __aenter__(self) -> Self:
                return self

            async def __aexit__(self, *_args: object) -> None:
                pass

            def __getattr__(self, name: str) -> Any:
                def enqueue(*args: Any, **kwargs: Any) -> 'Pipeline':
                    self.calls.append((name, args, kwargs))
                    return self
                return enqueue

            async def execute(self) -> list[Any]:
                return [await getattr(redis, name)(*args, **kwargs) for name, args, kwargs in self.calls]

        return Pipeline()


@pytest.fixture
def memory(monkeypatch: pytest.MonkeyPatch) -> MemoryRedis:
    redis = MemoryRedis()
    for module in (tokens, token_reason, jwt_module, auth_module, scan_module):
        monkeypatch.setattr(module, 'redis_client', redis)
    context = SimpleNamespace(ip='127.0.0.1', os='test', browser='test', device='test', client_type='web')
    monkeypatch.setattr(auth_module, 'ctx', context)
    monkeypatch.setattr(scan_module, 'ctx', context)
    monkeypatch.setattr(jwt_module, 'ctx', context)
    monkeypatch.setattr(jwt_module, 'get_jwt_user', AsyncMock(return_value=SimpleNamespace(id=7, is_superuser=False)))
    return redis


async def issue(kind: str, *, multi: bool = False, user_id: int = 7) -> NewToken:
    return await tokens.create_token_pair(user_id, multi_login=multi, client_type=LoginClientType(kind))


async def refresh(pair: NewToken) -> NewToken:
    return await tokens.create_new_token(pair.new_refresh_token, pair.session_uuid, 7, multi_login=False)


def request(
    kind: str, *, cookie: str | None = None, access: str | None = None, session: str | None = None,
) -> Request:
    headers = [(b'x-client-type', kind.encode())]
    if cookie:
        headers.append((b'cookie', cookie.encode()))
    if access:
        headers.append((b'authorization', f'Bearer {access}'.encode()))
    if session:
        headers.append((b'x-session-id', session.encode()))
    return Request({'type': 'http', 'headers': headers})


@pytest.mark.asyncio
async def test_four_clients_coexist_and_same_client_replaces_both_credentials(memory: MemoryRedis) -> None:
    initial = {kind: await issue(kind) for kind in LoginClientType}
    replacement = await issue('web')
    assert await tokens.get_user_sessions(7) == {
        replacement.session_uuid, *(pair.session_uuid for kind, pair in initial.items() if kind != 'web'),
    }
    with pytest.raises(errors.TokenError) as failure:
        await jwt_module.jwt_authentication(initial['web'].new_access_token)
    assert failure.value.data['auth_reason'] == 'session_replaced'
    with pytest.raises(errors.TokenError):
        await refresh(initial['web'])
    for kind in ('admin', 'miniapp', 'extension'):
        assert (await jwt_module.jwt_authentication(initial[kind].new_access_token)).id == 7


@pytest.mark.asyncio
async def test_refresh_preserves_session_and_other_clients(memory: MemoryRedis) -> None:
    web = await issue('web')
    mini = await issue('miniapp')
    await memory.delete(f'{settings.TOKEN_REDIS_PREFIX}:7:{web.session_uuid}')
    renewed = await refresh(web)
    assert renewed.session_uuid == web.session_uuid
    assert jwt_module.jwt_decode(renewed.new_access_token).client_type == 'web'
    assert await tokens.get_user_sessions(7) == {web.session_uuid, mini.session_uuid}
    with pytest.raises(errors.TokenError):
        await refresh(web)


@pytest.mark.asyncio
async def test_unlimited_exception_and_policy_reduction_keep_one_per_client(memory: MemoryRedis) -> None:
    older = await issue('web', multi=True)
    newer = await issue('web', multi=True)
    extensions = [await issue('extension', multi=True) for _ in range(3)]
    mini = await issue('miniapp', multi=True)
    assert len(await tokens.get_user_sessions(7)) == 6
    await tokens.enforce_single_session_per_client(7, current_session_uuid=older.session_uuid)
    assert await tokens.get_user_sessions(7) == {older.session_uuid, extensions[-1].session_uuid, mini.session_uuid}
    assert await token_reason.get_token_invalid_reason(7, newer.session_uuid) == 'policy_changed'


@pytest.mark.asyncio
async def test_concurrent_logins_leave_one_complete_pair_per_client(memory: MemoryRedis) -> None:
    pairs = await asyncio.gather(*(issue(kind) for _ in range(8) for kind in ('web', 'extension')))
    sessions = await tokens.get_user_sessions(7)
    assert len(sessions) == 2
    for pair in pairs:
        if pair.session_uuid in sessions:
            assert await memory.get(f'{settings.TOKEN_REDIS_PREFIX}:7:{pair.session_uuid}') == pair.new_access_token
            stored_refresh = await memory.get(f'{settings.TOKEN_REFRESH_REDIS_PREFIX}:7:{pair.session_uuid}')
            assert stored_refresh == pair.new_refresh_token
        else:
            assert await token_reason.get_token_invalid_reason(7, pair.session_uuid) == 'session_replaced'
            assert not await memory.exists(f'{settings.TOKEN_REFRESH_REDIS_PREFIX}:7:{pair.session_uuid}')


@pytest.mark.asyncio
async def test_logout_and_refresh_race_never_resurrects_session(memory: MemoryRedis) -> None:
    for _ in range(4):
        pair = await issue('web')
        await asyncio.gather(
            refresh(pair), tokens.revoke_token(7, pair.session_uuid, reason=token_reason.TokenInvalidReason.logout),
            return_exceptions=True,
        )
        assert not await tokens.get_user_sessions(7)
        with pytest.raises(errors.TokenError):
            await tokens.create_refresh_token(pair.session_uuid, 7, multi_login=False)


@pytest.mark.asyncio
async def test_password_reset_revokes_all_clients_and_accounts_are_isolated(memory: MemoryRedis) -> None:
    pairs = [await issue(kind) for kind in LoginClientType]
    other = await issue('web', user_id=8)
    await tokens.revoke_user_tokens(7, reason=token_reason.TokenInvalidReason.password_changed)
    assert not await tokens.get_user_sessions(7)
    assert await tokens.get_user_sessions(8) == {other.session_uuid}
    for pair in pairs:
        assert await token_reason.get_token_invalid_reason(7, pair.session_uuid) == 'password_changed'


@pytest.mark.asyncio
async def test_swagger_does_not_consume_or_replace_normal_slots(memory: MemoryRedis) -> None:
    swagger = await tokens.create_access_token(7, multi_login=False, swagger=True)
    web = await issue('web')
    await issue('extension')
    assert await memory.exists(f'{settings.TOKEN_REDIS_PREFIX}:7:{swagger.session_uuid}')
    assert web.session_uuid in await tokens.get_user_sessions(7)
    assert swagger.session_uuid not in await tokens.get_user_sessions(7)


@pytest.mark.asyncio
async def test_unknown_client_rejected_and_non_staff_cannot_use_admin_slot(memory: MemoryRedis) -> None:
    with pytest.raises(errors.RequestError):
        get_login_client_type(request('web-2'))
    user = SimpleNamespace(status=1, is_staff=False)
    with pytest.raises(errors.AuthorizationError, match='后台登录权限'):
        await auth_module.auth_service.issue_login_token(
            db=AsyncMock(), response=Response(), user=user, client_type=LoginClientType.admin,
        )
    assert not await tokens.get_user_sessions(7)


@pytest.mark.asyncio
async def test_refresh_cookie_isolation_and_session_matching(memory: MemoryRedis) -> None:
    web = await issue('web')
    mini = await issue('miniapp')
    cookies = f'fba_refresh_token_web={web.new_refresh_token}; fba_refresh_token_miniapp={mini.new_refresh_token}'
    raw, payload, kind = auth_module.AuthService._refresh_credentials(request('web', cookie=cookies), None)
    assert raw == web.new_refresh_token and kind == 'web' and payload.session_uuid == web.session_uuid
    with pytest.raises(errors.TokenError):
        auth_module.AuthService._refresh_credentials(request('admin', cookie=cookies), None)
    with pytest.raises(errors.TokenError):
        auth_module.AuthService._refresh_credentials(request('web', cookie=cookies, session=mini.session_uuid), None)
    with pytest.raises(errors.TokenError):
        auth_module.AuthService._refresh_credentials(
            request('miniapp', cookie=f'fba_refresh_token_miniapp={web.new_refresh_token}'), None,
        )


@pytest.mark.asyncio
async def test_stale_logout_preserves_other_sessions_and_cookies(memory: MemoryRedis) -> None:
    old = await issue('web')
    current = await issue('web')
    mini = await issue('miniapp')
    response = Response()
    await auth_module.auth_service.logout(
        request=request(
            'web', cookie=f'fba_refresh_token_web={current.new_refresh_token}', access=old.new_access_token,
        ),
        response=response,
    )
    assert not response.headers.getlist('set-cookie')
    assert await tokens.get_user_sessions(7) == {current.session_uuid, mini.session_uuid}


@pytest.mark.asyncio
async def test_legacy_sessions_cannot_gain_extra_slots_by_refreshing(memory: MemoryRedis) -> None:
    pair = await issue('web', multi=True)
    legacy = jwt_module.jwt_encode({
        'sub': '7', 'session_uuid': pair.session_uuid,
        'exp': (timezone.now() + timedelta(days=1)).timestamp(),
    })
    await memory.set(f'{settings.TOKEN_REDIS_PREFIX}:7:{pair.session_uuid}', legacy)
    await memory.set(f'{settings.TOKEN_REFRESH_REDIS_PREFIX}:7:{pair.session_uuid}', legacy)
    with pytest.raises(errors.TokenError):
        await tokens.create_new_token(legacy, pair.session_uuid, 7, multi_login=True)
    replacement = await issue('miniapp')
    assert await tokens.get_user_sessions(7) == {replacement.session_uuid}


@pytest.mark.asyncio
async def test_scan_isolates_target_credentials(memory: MemoryRedis, monkeypatch: pytest.MonkeyPatch) -> None:
    user = SimpleNamespace(
        id=7, uuid='user-7', username='test', nickname='test', status=1,
        is_staff=True, is_superuser=False, is_multi_login=False, dept_id=None,
        avatar=None, email=None, phone=None, join_time=timezone.now(), last_login_time=timezone.now(),
    )
    monkeypatch.setattr(auth_module.user_dao, 'update_login_time', AsyncMock())
    monkeypatch.setattr(auth_module, 'publish', AsyncMock())
    mobile = await issue('miniapp')
    scene = {'status': 'PENDING', 'client_type': 'web', 'session_info': {'ip': 'desktop-ip'}}
    await memory.set(f'{scan_module.SCAN_REDIS_PREFIX}scene', json.dumps(scene))

    async def fake_wechat(**kwargs: Any) -> GetLoginToken:
        assert kwargs['client_type'] == 'web'
        return await auth_module.auth_service.issue_login_token(
            db=AsyncMock(), response=kwargs['response'], user=user,
            client_type=kwargs['client_type'], session_info=kwargs['session_info'],
        )

    monkeypatch.setattr(scan_module.oauth2_service, 'wechat_miniapp_login', fake_wechat)
    phone_response = Response()
    await scan_module.wechat_scan_service.confirm_scan(
        db=AsyncMock(), response=phone_response, background_tasks=BackgroundTasks(), scene_id='scene', code='wx-code',
    )
    assert not phone_response.headers.getlist('set-cookie')
    assert mobile.session_uuid in await tokens.get_user_sessions(7)
    with pytest.raises(errors.RequestError):
        await scan_module.wechat_scan_service.get_scan_status(
            'scene', response=Response(), client_type=LoginClientType.extension,
        )
    desktop_response = Response()
    result = await scan_module.wechat_scan_service.get_scan_status('scene', response=desktop_response)
    assert result['token']['client_type'] == 'web'
    assert result['token']['refresh_token'] is None
    assert desktop_response.headers['set-cookie'].startswith(f'{refresh_cookie_key(LoginClientType.web)}=')
    assert 'HttpOnly' in desktop_response.headers['set-cookie']
    assert (await scan_module.wechat_scan_service.get_scan_status('scene', response=Response()))['status'] == 'EXPIRED'


@pytest.mark.asyncio
async def test_exchange_issues_independent_session(memory: MemoryRedis, monkeypatch: pytest.MonkeyPatch) -> None:
    source = await issue('web')
    captured = {}

    async def issue_extension(**kwargs: Any) -> NewToken:
        captured.update(kwargs)
        return await issue(kwargs['client_type'])

    monkeypatch.setattr(auth_module.user_dao, 'get', AsyncMock(return_value=SimpleNamespace(id=7)))
    monkeypatch.setattr(auth_module.auth_service, 'issue_login_token', issue_extension)
    result = await auth_module.auth_service.exchange_extension_session(
        db=AsyncMock(), request=request('extension', access=source.new_access_token), response=Response(),
    )
    assert captured['client_type'] == 'extension'
    assert result.session_uuid != source.session_uuid
    await tokens.revoke_token(7, result.session_uuid, reason=token_reason.TokenInvalidReason.logout)
    assert (await jwt_module.jwt_authentication(source.new_access_token)).id == 7


@pytest.mark.asyncio
async def test_production_disallows_debug_login_and_untyped_jwt(
    memory: MemoryRedis, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, 'ENVIRONMENT', 'prod')
    verify = AsyncMock()
    monkeypatch.setattr(auth_module.auth_service, 'user_verify', verify)
    with pytest.raises(errors.NotFoundError):
        await auth_module.auth_service.swagger_login(
            db=AsyncMock(), obj=HTTPBasicCredentials(username='test', password='test'),
        )
    verify.assert_not_awaited()
    debug_token = await tokens.create_access_token(7, multi_login=False, swagger=True)
    with pytest.raises(errors.TokenError) as failure:
        await jwt_module.jwt_authentication(debug_token.access_token)
    assert failure.value.data['auth_reason'] == 'policy_changed'


@pytest.mark.asyncio
async def test_development_debug_login_requires_staff(memory: MemoryRedis, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, 'ENVIRONMENT', 'dev')
    monkeypatch.setattr(
        auth_module.auth_service, 'user_verify', AsyncMock(return_value=(SimpleNamespace(is_staff=False), None)),
    )
    with pytest.raises(errors.AuthorizationError):
        await auth_module.auth_service.swagger_login(
            db=AsyncMock(), obj=HTTPBasicCredentials(username='test', password='test'),
        )
    assert not await tokens.get_user_sessions(7)
