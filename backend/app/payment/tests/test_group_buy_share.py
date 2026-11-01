#!/usr/bin/env python3
import asyncio
import base64
import inspect
import json

from collections.abc import Callable
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Literal, Self
from unittest.mock import AsyncMock

import httpx
import pytest

from fastapi.routing import APIRoute
from pydantic import ValidationError
from redis.exceptions import LockError
from sqlalchemy.dialects import postgresql

import backend.app.payment.service.group_buy_share_service as share_module

from backend.app.payment.api.v1 import group_buy as group_buy_api
from backend.app.payment.crud.crud_group_buy import group_buy_dao
from backend.app.payment.schema.group_buy import GroupBuyShareCodeResult, GroupBuyShareLinkResult
from backend.app.payment.service.group_buy_share_service import group_buy_share_service
from backend.common.exception import errors
from backend.common.security.jwt import DependsJwtAuth
from backend.utils.timezone import timezone as real_timezone

CODE = 'abcdef0123456789abcdef01'
USER_ID = 7
PAGE = 'pkg/mine/group-buy/index'
TOKEN = 'ACCESS_SECRET_TOKEN'
OPS = ['qrcode', 'short', 'url']
DAO_PATH = 'backend.app.payment.service.group_buy_share_service.group_buy_dao.share_context'


class _Clock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def now(self) -> datetime:
        return self.value


class _FakeRedis:
    def __init__(
        self,
        *,
        initial: dict[str, str] | None = None,
        lock_error: bool = False,
        on_lock: Callable[[], None] | None = None,
    ) -> None:
        self.data = dict(initial or {})
        self.lock_error = lock_error
        self._on_lock = on_lock
        self.get_keys: list[str] = []
        self.set_calls: list[tuple[str, str, int | None]] = []
        self.locks: list[tuple[str, int | None, int | None]] = []
        self.guard = asyncio.Lock()

    async def get(self, key: str) -> str | None:
        self.get_keys.append(key)
        return self.data.get(key)

    async def set(self, key: str, value: str, *, ex: int | None = None) -> bool:
        self.set_calls.append((key, value, ex))
        self.data[key] = value
        return True

    def lock(
        self, name: str, *, timeout: int | None = None, blocking_timeout: int | None = None
    ) -> '_FakeLock':
        self.locks.append((name, timeout, blocking_timeout))
        return _FakeLock(self, on_enter=self._on_lock)


class _FakeLock:
    def __init__(self, redis: _FakeRedis, *, on_enter: Callable[[], None] | None = None) -> None:
        self._redis = redis
        self._on_enter = on_enter
        self._held = False

    async def __aenter__(self) -> Self:
        if self._redis.lock_error:
            raise LockError('lock is held by a concurrent request')
        await self._redis.guard.acquire()
        self._held = True
        if self._on_enter is not None:
            self._on_enter()
        await asyncio.sleep(0)
        return self

    async def __aexit__(self, *exc_info: object) -> bool:
        if self._held:
            self._held = False
            self._redis.guard.release()
        return False


class _FakeWechat:
    def __init__(
        self,
        *,
        response: httpx.Response | None = None,
        handler: Callable[[httpx.Request], object] | None = None,
    ) -> None:
        self._response = response
        self._handler = handler
        self.requests: list[httpx.Request] = []

    async def _handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self._handler is not None:
            result = self._handler(request)
            if inspect.isawaitable(result):
                return await result
            return result
        if self._response is None:
            raise AssertionError('fake wechat response is required')
        return self._response

    def install(self, monkeypatch: pytest.MonkeyPatch) -> None:
        real_client = httpx.AsyncClient
        transport = httpx.MockTransport(self._handle)

        def factory(*args: object, **kwargs: object) -> httpx.AsyncClient:
            return real_client(transport=transport)

        monkeypatch.setattr(share_module.httpx, 'AsyncClient', factory)


class _MappingResult:
    def __init__(self, row: dict | None) -> None:
        self._row = row

    def one_or_none(self) -> dict | None:
        return self._row


class _ExecuteResult:
    def __init__(self, row: dict | None) -> None:
        self._row = row

    def mappings(self) -> _MappingResult:
        return _MappingResult(self._row)


def _context(
    *,
    deadline: datetime | None,
    status: str = 'forming',
    member_status: str | None = 'paid',
    snapshot: dict | None = None,
) -> dict:
    return {
        'status': status,
        'deadline': deadline,
        'snapshot': {'base': {'name': '考研·SVIP 年卡'}} if snapshot is None else snapshot,
        'member_status': member_status,
    }


def _patch_dao(monkeypatch: pytest.MonkeyPatch, *contexts: dict | None) -> AsyncMock:
    mock = AsyncMock(return_value=contexts[0]) if len(contexts) == 1 else AsyncMock(side_effect=list(contexts))
    monkeypatch.setattr(DAO_PATH, mock)
    return mock


def _patch_redis(
    monkeypatch: pytest.MonkeyPatch,
    *,
    initial: dict[str, str] | None = None,
    lock_error: bool = False,
    on_lock: Callable[[], None] | None = None,
) -> _FakeRedis:
    fake = _FakeRedis(initial=initial, lock_error=lock_error, on_lock=on_lock)
    monkeypatch.setattr(share_module, 'redis_client', fake)
    return fake


def _patch_token(monkeypatch: pytest.MonkeyPatch) -> str:
    monkeypatch.setattr(
        share_module,
        'WechatScanService',
        SimpleNamespace(get_access_token=AsyncMock(return_value=TOKEN)),
    )
    return TOKEN


def _image_response(content: bytes = b'\x89PNG-invite', content_type: str = 'image/png') -> httpx.Response:
    return httpx.Response(200, content=content, headers={'content-type': content_type})


def _json_response(payload: object, *, status: int = 200, raw: bytes | None = None) -> httpx.Response:
    content = raw if raw is not None else json.dumps(payload, ensure_ascii=False).encode('utf-8')
    return httpx.Response(status, content=content, headers={'content-type': 'application/json'})


def _raw_response(content: bytes, content_type: str = 'text/plain', *, status: int = 200) -> httpx.Response:
    return httpx.Response(status, content=content, headers={'content-type': content_type})


def _wechat_router(request: httpx.Request) -> httpx.Response:
    path = request.url.path
    if path.endswith('getwxacodeunlimit'):
        return _image_response()
    if path.endswith('createwxaqrcode'):
        return _image_response(content_type='image/jpeg')
    if path.endswith('genwxashortlink'):
        return _json_response({'link': '#小程序://Invite'})
    return _json_response({'url_link': 'https://wxaurl.cn/Invite'})


def _success_response(op: str) -> httpx.Response:
    if op == 'qrcode':
        return _image_response()
    if op == 'short':
        return _json_response({'link': '#小程序://Invite'})
    return _json_response({'url_link': 'https://wxaurl.cn/Invite'})


def _cache_key(op: str) -> str:
    if op == 'qrcode':
        return f'payment:group-buy:share-code:miniapp:trial:{CODE}'
    if op == 'short':
        return f'payment:group-buy:share-link:short:release:{CODE}'
    return f'payment:group-buy:share-link:url:release:{CODE}'


def _call(op: str, db: object, *, code: str = CODE) -> dict:
    async def scenario() -> dict:
        if op == 'qrcode':
            return await group_buy_share_service.qrcode(db, code=code, user_id=USER_ID, style='miniapp')
        if op == 'short':
            return await group_buy_share_service.link(db, code=code, user_id=USER_ID, kind='short')
        return await group_buy_share_service.link(db, code=code, user_id=USER_ID, kind='url')

    return asyncio.run(scenario())


def _call_qrcode_style(db: object, style: str) -> dict:
    return asyncio.run(group_buy_share_service.qrcode(db, code=CODE, user_id=USER_ID, style=style))


def _call_link_kind(db: object, kind: str) -> dict:
    return asyncio.run(group_buy_share_service.link(db, code=CODE, user_id=USER_ID, kind=kind))


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> _Clock:
    fake = _Clock(real_timezone.now().replace(microsecond=0))
    monkeypatch.setattr(share_module, 'timezone', fake)
    return fake


@pytest.fixture
def token(monkeypatch: pytest.MonkeyPatch) -> str:
    return _patch_token(monkeypatch)


def test_miniapp_qrcode_success_shape_path_and_ttl(
    clock: _Clock, monkeypatch: pytest.MonkeyPatch, token: str
) -> None:
    deadline = clock.value + timedelta(hours=2)
    _patch_dao(monkeypatch, _context(deadline=deadline))
    redis = _patch_redis(monkeypatch)
    content = b'\x89PNG-invite'
    wechat = _FakeWechat(response=_image_response(content))
    wechat.install(monkeypatch)

    result = _call('qrcode', SimpleNamespace())

    assert result == {
        'data_url': f'data:image/png;base64,{base64.b64encode(content).decode()}',
        'share_code': CODE,
        'deadline': deadline.isoformat(),
        'style': 'miniapp',
        'env_version': 'trial',
    }
    request = wechat.requests[0]
    assert request.url.path == '/wxa/getwxacodeunlimit'
    assert request.url.params['access_token'] == token
    payload = json.loads(request.content)
    assert payload['scene'] == f'gb_{CODE}'
    assert payload['page'] == PAGE
    assert payload['width'] == 430
    assert payload['env_version'] == 'trial'
    assert payload['check_path'] is False
    key = f'payment:group-buy:share-code:miniapp:trial:{CODE}'
    assert redis.locks == [(f'{key}:lock', 45, 3)]
    stored_key, stored_value, ttl = redis.set_calls[0]
    assert stored_key == key
    assert json.loads(stored_value) == result
    assert ttl == int((deadline - clock.value).total_seconds())
    assert 0 < ttl <= 7200
    assert token not in json.dumps(result, ensure_ascii=False)
    assert 'order' not in json.dumps(result, ensure_ascii=False)


def test_square_qrcode_is_release_and_uses_shipped_page(
    clock: _Clock, monkeypatch: pytest.MonkeyPatch, token: str
) -> None:
    deadline = clock.value + timedelta(hours=2)
    _patch_dao(monkeypatch, _context(deadline=deadline))
    redis = _patch_redis(monkeypatch)
    wechat = _FakeWechat(response=_image_response(content_type='image/jpeg'))
    wechat.install(monkeypatch)

    result = asyncio.run(
        group_buy_share_service.qrcode(SimpleNamespace(), code=CODE, user_id=USER_ID, style='square')
    )

    assert result['style'] == 'square'
    assert result['env_version'] == 'release'
    assert result['data_url'].startswith('data:image/jpeg;base64,')
    payload = json.loads(wechat.requests[0].content)
    assert wechat.requests[0].url.path == '/cgi-bin/wxaapp/createwxaqrcode'
    assert payload == {'path': f'{PAGE}?group_code={CODE}', 'width': 430}
    key = f'payment:group-buy:share-code:square:release:{CODE}'
    assert {item[0] for item in redis.set_calls} == {key}


def test_short_link_success_shape_path_and_ttl(
    clock: _Clock, monkeypatch: pytest.MonkeyPatch, token: str
) -> None:
    deadline = clock.value + timedelta(hours=2)
    _patch_dao(monkeypatch, _context(deadline=deadline))
    redis = _patch_redis(monkeypatch)
    wechat = _FakeWechat(response=_success_response('short'))
    wechat.install(monkeypatch)

    result = _call('short', SimpleNamespace())

    assert result == {
        'link': '#小程序://Invite',
        'kind': 'short',
        'share_code': CODE,
        'deadline': deadline.isoformat(),
        'expires_at': (clock.value + timedelta(days=30)).isoformat(),
    }
    payload = json.loads(wechat.requests[0].content)
    assert wechat.requests[0].url.path == '/wxa/genwxashortlink'
    assert payload['page_url'] == f'{PAGE}?group_code={CODE}'
    assert payload['page_title'] == '一起拼「考研·SVIP 年卡」'[:20]
    assert len(payload['page_title']) <= 20
    assert payload['is_permanent'] is False
    key = f'payment:group-buy:share-link:short:release:{CODE}'
    stored_key, stored_value, ttl = redis.set_calls[0]
    assert stored_key == key
    assert json.loads(stored_value) == result
    assert ttl == int((deadline - clock.value).total_seconds())
    assert token not in json.dumps(result, ensure_ascii=False)
    assert 'order' not in json.dumps(result, ensure_ascii=False)


def test_url_link_success_shape_path_and_ttl(clock: _Clock, monkeypatch: pytest.MonkeyPatch, token: str) -> None:
    deadline = clock.value + timedelta(hours=2)
    _patch_dao(monkeypatch, _context(deadline=deadline))
    redis = _patch_redis(monkeypatch)
    wechat = _FakeWechat(response=_success_response('url'))
    wechat.install(monkeypatch)

    result = _call('url', SimpleNamespace())

    assert result == {
        'link': 'https://wxaurl.cn/Invite',
        'kind': 'url',
        'share_code': CODE,
        'deadline': deadline.isoformat(),
        'expires_at': deadline.isoformat(),
    }
    assert 'url_link' not in result
    payload = json.loads(wechat.requests[0].content)
    assert wechat.requests[0].url.path == '/wxa/generate_urllink'
    assert payload['path'] == PAGE
    assert payload['query'] == f'group_code={CODE}'
    assert payload['expire_type'] == 0
    assert payload['expire_time'] == int(deadline.timestamp())
    assert payload['env_version'] == 'release'
    key = f'payment:group-buy:share-link:url:release:{CODE}'
    stored_key, _, ttl = redis.set_calls[0]
    assert stored_key == key
    assert ttl == int((deadline - clock.value).total_seconds())
    assert token not in json.dumps(result, ensure_ascii=False)


def test_short_link_ttl_is_capped_at_thirty_days(
    clock: _Clock, monkeypatch: pytest.MonkeyPatch, token: str
) -> None:
    deadline = clock.value + timedelta(days=40)
    _patch_dao(monkeypatch, _context(deadline=deadline))
    redis = _patch_redis(monkeypatch)
    wechat = _FakeWechat(response=_success_response('short'))
    wechat.install(monkeypatch)

    _call('short', SimpleNamespace())

    _, _, ttl = redis.set_calls[0]
    assert ttl == int(timedelta(days=30).total_seconds())
    assert ttl <= int((deadline - clock.value).total_seconds())


def test_short_link_still_works_under_one_minute(
    clock: _Clock, monkeypatch: pytest.MonkeyPatch, token: str
) -> None:
    deadline = clock.value + timedelta(seconds=30)
    _patch_dao(monkeypatch, _context(deadline=deadline))
    redis = _patch_redis(monkeypatch)
    wechat = _FakeWechat(response=_success_response('short'))
    wechat.install(monkeypatch)

    result = _call('short', SimpleNamespace())

    assert result['link'] == '#小程序://Invite'
    _, _, ttl = redis.set_calls[0]
    assert ttl == 30


def test_url_link_rejects_near_expiry_without_http(clock: _Clock, monkeypatch: pytest.MonkeyPatch, token: str) -> None:
    deadline = clock.value + timedelta(seconds=30)
    _patch_dao(monkeypatch, _context(deadline=deadline))
    redis = _patch_redis(monkeypatch)
    wechat = _FakeWechat(response=_success_response('url'))
    wechat.install(monkeypatch)

    with pytest.raises(errors.RequestError) as exc_info:
        _call('url', SimpleNamespace())

    assert '不足一分钟' in exc_info.value.msg
    assert wechat.requests == []
    assert redis.set_calls == []
    assert redis.locks != []


@pytest.mark.parametrize('op', OPS)
@pytest.mark.parametrize(
    'code',
    ['', 'abc', CODE.upper(), CODE[:-1], 'g' * 24, f'{CODE}\n', '0123456789abcdef0123456g'],
)
def test_invalid_code_rejected_before_dao_cache_and_http(
    clock: _Clock, monkeypatch: pytest.MonkeyPatch, token: str, op: str, code: str
) -> None:
    _patch_dao(monkeypatch, _context(deadline=clock.value + timedelta(hours=1)))
    redis = _patch_redis(monkeypatch, initial={_cache_key(op): '{"link":"cached"}'})
    wechat = _FakeWechat(response=_success_response(op))
    wechat.install(monkeypatch)

    with pytest.raises(errors.RequestError) as exc_info:
        _call(op, SimpleNamespace(), code=code)

    assert '拼团码无效' in exc_info.value.msg
    assert redis.get_keys == []
    assert redis.locks == []
    assert redis.set_calls == []
    assert wechat.requests == []


@pytest.mark.parametrize('style', ['bad', 'MINIAPP', ''])
def test_unknown_qrcode_style_rejected_before_any_io(
    clock: _Clock, monkeypatch: pytest.MonkeyPatch, token: str, style: str
) -> None:
    _patch_dao(monkeypatch, _context(deadline=clock.value + timedelta(hours=1)))
    redis = _patch_redis(monkeypatch)
    wechat = _FakeWechat(response=_image_response())
    wechat.install(monkeypatch)

    with pytest.raises(errors.RequestError) as exc_info:
        _call_qrcode_style(SimpleNamespace(), style)

    assert '不支持的邀请二维码类型' in exc_info.value.msg
    assert redis.get_keys == []
    assert wechat.requests == []


@pytest.mark.parametrize('kind', ['bad', 'SHORT', ''])
def test_unknown_link_kind_rejected_before_any_io(
    clock: _Clock, monkeypatch: pytest.MonkeyPatch, token: str, kind: str
) -> None:
    _patch_dao(monkeypatch, _context(deadline=clock.value + timedelta(hours=1)))
    redis = _patch_redis(monkeypatch)
    wechat = _FakeWechat(response=_success_response('short'))
    wechat.install(monkeypatch)

    with pytest.raises(errors.RequestError) as exc_info:
        _call_link_kind(SimpleNamespace(), kind)

    assert '不支持的邀请链接类型' in exc_info.value.msg
    assert redis.get_keys == []
    assert wechat.requests == []


@pytest.mark.parametrize('op', OPS)
@pytest.mark.parametrize('status', ['draft', 'succeeded', 'expired', 'cancelled'])
def test_non_forming_team_rejected_before_cache_and_http(
    clock: _Clock, monkeypatch: pytest.MonkeyPatch, token: str, op: str, status: str
) -> None:
    dao = _patch_dao(monkeypatch, _context(deadline=clock.value + timedelta(hours=1), status=status))
    redis = _patch_redis(monkeypatch, initial={_cache_key(op): '{"link":"cached"}'})
    wechat = _FakeWechat(response=_success_response(op))
    wechat.install(monkeypatch)

    with pytest.raises(errors.RequestError) as exc_info:
        _call(op, SimpleNamespace())

    assert '进行中且未到期' in exc_info.value.msg
    dao.assert_awaited_once()
    assert redis.get_keys == []
    assert redis.locks == []
    assert redis.set_calls == []
    assert wechat.requests == []


def test_missing_team_rejected_before_cache_and_http(
    clock: _Clock, monkeypatch: pytest.MonkeyPatch, token: str
) -> None:
    dao = _patch_dao(monkeypatch, None)
    redis = _patch_redis(monkeypatch, initial={_cache_key('qrcode'): '{"data_url":"cached"}'})
    wechat = _FakeWechat(response=_image_response())
    wechat.install(monkeypatch)

    with pytest.raises(errors.RequestError):
        _call('qrcode', SimpleNamespace())

    dao.assert_awaited_once()
    assert redis.get_keys == []
    assert redis.set_calls == []
    assert wechat.requests == []


@pytest.mark.parametrize('op', OPS)
@pytest.mark.parametrize('deadline_delta', [None, 0, -1])
def test_missing_or_ended_deadline_rejected_before_cache_and_http(
    clock: _Clock, monkeypatch: pytest.MonkeyPatch, token: str, op: str, deadline_delta: int | None
) -> None:
    deadline = None if deadline_delta is None else clock.value + timedelta(seconds=deadline_delta)
    dao = _patch_dao(monkeypatch, _context(deadline=deadline))
    redis = _patch_redis(monkeypatch, initial={_cache_key(op): '{"link":"cached"}'})
    wechat = _FakeWechat(response=_success_response(op))
    wechat.install(monkeypatch)

    with pytest.raises(errors.RequestError):
        _call(op, SimpleNamespace())

    dao.assert_awaited_once()
    assert redis.get_keys == []
    assert redis.locks == []
    assert redis.set_calls == []
    assert wechat.requests == []


@pytest.mark.parametrize('op', OPS)
@pytest.mark.parametrize('member_status', [None, 'reserved', 'expired', 'refund_pending', 'refunded'])
def test_other_or_unpaid_member_rejected_before_cache_and_http(
    clock: _Clock, monkeypatch: pytest.MonkeyPatch, token: str, op: str, member_status: str | None
) -> None:
    dao = _patch_dao(
        monkeypatch,
        _context(deadline=clock.value + timedelta(hours=1), member_status=member_status),
    )
    redis = _patch_redis(monkeypatch, initial={_cache_key(op): '{"link":"cached"}'})
    wechat = _FakeWechat(response=_success_response(op))
    wechat.install(monkeypatch)

    with pytest.raises(errors.ForbiddenError) as exc_info:
        _call(op, SimpleNamespace())

    assert '本人参团付款' in exc_info.value.msg
    dao.assert_awaited_once()
    assert redis.get_keys == []
    assert redis.locks == []
    assert redis.set_calls == []
    assert wechat.requests == []


def test_cache_hit_authenticates_before_returning(clock: _Clock, monkeypatch: pytest.MonkeyPatch, token: str) -> None:
    deadline = clock.value + timedelta(hours=2)
    cached = {
        'data_url': 'data:image/png;base64,Y2FjaGVk',
        'share_code': CODE,
        'deadline': deadline.isoformat(),
        'style': 'miniapp',
        'env_version': 'trial',
    }
    key = _cache_key('qrcode')
    dao = _patch_dao(monkeypatch, _context(deadline=deadline))
    redis = _patch_redis(monkeypatch, initial={key: json.dumps(cached)})
    wechat = _FakeWechat(response=_image_response())
    wechat.install(monkeypatch)

    assert _call('qrcode', SimpleNamespace()) == cached
    dao.assert_awaited_once()
    assert redis.get_keys == [key]
    assert redis.locks == []
    assert redis.set_calls == []
    assert wechat.requests == []


@pytest.mark.parametrize('op', OPS)
def test_state_change_inside_lock_rejects_without_http_or_cache(
    clock: _Clock, monkeypatch: pytest.MonkeyPatch, token: str, op: str
) -> None:
    deadline = clock.value + timedelta(hours=2)
    dao = _patch_dao(
        monkeypatch,
        _context(deadline=deadline),
        _context(deadline=deadline, status='succeeded'),
    )
    redis = _patch_redis(monkeypatch)
    wechat = _FakeWechat(response=_success_response(op))
    wechat.install(monkeypatch)

    with pytest.raises(errors.RequestError):
        _call(op, SimpleNamespace())

    assert dao.await_count == 2
    assert redis.locks != []
    assert redis.set_calls == []
    assert wechat.requests == []


@pytest.mark.parametrize('op', OPS)
def test_lock_wait_until_deadline_rejects_without_http_or_cache(
    clock: _Clock, monkeypatch: pytest.MonkeyPatch, token: str, op: str
) -> None:
    deadline = clock.value + timedelta(seconds=120)
    dao = _patch_dao(monkeypatch, _context(deadline=deadline))
    redis = _patch_redis(monkeypatch, on_lock=lambda: setattr(clock, 'value', deadline))
    wechat = _FakeWechat(response=_success_response(op))
    wechat.install(monkeypatch)

    with pytest.raises(errors.RequestError):
        _call(op, SimpleNamespace())

    assert dao.await_count == 2
    assert redis.locks != []
    assert redis.set_calls == []
    assert wechat.requests == []


@pytest.mark.parametrize('op', OPS)
def test_state_change_while_supplier_responds_rejects_and_skips_cache(
    clock: _Clock, monkeypatch: pytest.MonkeyPatch, token: str, op: str
) -> None:
    deadline = clock.value + timedelta(hours=2)
    dao = _patch_dao(
        monkeypatch,
        _context(deadline=deadline),
        _context(deadline=deadline),
        _context(deadline=deadline, status='expired'),
    )
    redis = _patch_redis(monkeypatch)
    wechat = _FakeWechat(response=_success_response(op))
    wechat.install(monkeypatch)

    with pytest.raises(errors.RequestError):
        _call(op, SimpleNamespace())

    assert dao.await_count == 3
    assert len(wechat.requests) == 1
    assert redis.set_calls == []


def test_cache_keys_isolate_style_kind_and_environment(
    clock: _Clock, monkeypatch: pytest.MonkeyPatch, token: str
) -> None:
    deadline = clock.value + timedelta(hours=2)
    _patch_dao(monkeypatch, _context(deadline=deadline))
    redis = _patch_redis(monkeypatch)
    wechat = _FakeWechat(handler=_wechat_router)
    wechat.install(monkeypatch)
    db = SimpleNamespace()

    async def scenario() -> tuple[list[dict], list[dict]]:
        first = [
            await group_buy_share_service.qrcode(db, code=CODE, user_id=USER_ID, style='miniapp'),
            await group_buy_share_service.qrcode(db, code=CODE, user_id=USER_ID, style='square'),
            await group_buy_share_service.link(db, code=CODE, user_id=USER_ID, kind='short'),
            await group_buy_share_service.link(db, code=CODE, user_id=USER_ID, kind='url'),
        ]
        second = [
            await group_buy_share_service.qrcode(db, code=CODE, user_id=USER_ID, style='miniapp'),
            await group_buy_share_service.qrcode(db, code=CODE, user_id=USER_ID, style='square'),
            await group_buy_share_service.link(db, code=CODE, user_id=USER_ID, kind='short'),
            await group_buy_share_service.link(db, code=CODE, user_id=USER_ID, kind='url'),
        ]
        return first, second

    first, second = asyncio.run(scenario())

    assert second == first
    assert len(wechat.requests) == 4
    assert {item[0] for item in redis.set_calls} == {
        f'payment:group-buy:share-code:miniapp:trial:{CODE}',
        f'payment:group-buy:share-code:square:release:{CODE}',
        f'payment:group-buy:share-link:short:release:{CODE}',
        f'payment:group-buy:share-link:url:release:{CODE}',
    }
    assert len(redis.set_calls) == 4
    assert all(ttl is not None and ttl > 0 for _, _, ttl in redis.set_calls)


def test_production_miniapp_uses_release_key_and_version(
    clock: _Clock, monkeypatch: pytest.MonkeyPatch, token: str
) -> None:
    deadline = clock.value + timedelta(hours=2)
    monkeypatch.setattr(share_module.settings, 'ENVIRONMENT', 'prod')
    _patch_dao(monkeypatch, _context(deadline=deadline))
    trial_key = f'payment:group-buy:share-code:miniapp:trial:{CODE}'
    redis = _patch_redis(monkeypatch, initial={trial_key: '{"data_url":"trial-cache"}'})
    wechat = _FakeWechat(response=_image_response())
    wechat.install(monkeypatch)

    result = _call('qrcode', SimpleNamespace())

    assert result['env_version'] == 'release'
    payload = json.loads(wechat.requests[0].content)
    assert payload['env_version'] == 'release'
    assert payload['check_path'] is True
    release_key = f'payment:group-buy:share-code:miniapp:release:{CODE}'
    assert {item[0] for item in redis.set_calls} == {release_key}
    assert trial_key not in redis.get_keys


def test_concurrent_identical_requests_merge_to_single_supplier_call(
    clock: _Clock, monkeypatch: pytest.MonkeyPatch, token: str
) -> None:
    deadline = clock.value + timedelta(hours=2)
    _patch_dao(monkeypatch, _context(deadline=deadline))
    redis = _patch_redis(monkeypatch)
    wechat = _FakeWechat(handler=_wechat_router)
    wechat.install(monkeypatch)
    db = SimpleNamespace()

    async def scenario() -> list[dict]:
        return await asyncio.gather(
            group_buy_share_service.link(db, code=CODE, user_id=USER_ID, kind='short'),
            group_buy_share_service.link(db, code=CODE, user_id=USER_ID, kind='short'),
        )

    results = asyncio.run(scenario())

    assert results[0] == results[1]
    assert len(wechat.requests) == 1
    assert len(redis.set_calls) == 1


@pytest.mark.parametrize('op', OPS)
def test_lock_contention_error_is_translated_without_leak(
    clock: _Clock, monkeypatch: pytest.MonkeyPatch, token: str, op: str
) -> None:
    _patch_dao(monkeypatch, _context(deadline=clock.value + timedelta(hours=2)))
    redis = _patch_redis(monkeypatch, lock_error=True)
    wechat = _FakeWechat(response=_success_response(op))
    wechat.install(monkeypatch)

    with pytest.raises(errors.RequestError) as exc_info:
        _call(op, SimpleNamespace())

    assert '正在生成' in exc_info.value.msg
    assert token not in exc_info.value.msg
    assert redis.set_calls == []
    assert wechat.requests == []


def test_http_failure_returns_safe_gateway_error(
    clock: _Clock, monkeypatch: pytest.MonkeyPatch, token: str
) -> None:
    _patch_dao(monkeypatch, _context(deadline=clock.value + timedelta(hours=2)))
    redis = _patch_redis(monkeypatch)

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f'cannot connect {request.url}')

    wechat = _FakeWechat(handler=handler)
    wechat.install(monkeypatch)

    with pytest.raises(errors.GatewayError) as exc_info:
        _call('short', SimpleNamespace())

    msg = exc_info.value.msg
    assert '暂不可用' in msg
    assert token not in msg
    assert 'access_token' not in msg
    assert 'api.weixin.qq.com' not in msg
    assert redis.set_calls == []


@pytest.mark.parametrize('op', OPS)
@pytest.mark.parametrize(
    ['errcode', 'fragment'],
    [
        [40165, '发布'],
        [85079, '发布'],
        [43104, '权限'],
        [40002, '权限'],
        [45009, '失败'],
        [99999, '失败'],
    ],
)
def test_supplier_errors_are_mapped_to_safe_messages(
    clock: _Clock,
    monkeypatch: pytest.MonkeyPatch,
    token: str,
    op: str,
    errcode: int,
    fragment: str,
) -> None:
    _patch_dao(monkeypatch, _context(deadline=clock.value + timedelta(hours=2)))
    redis = _patch_redis(monkeypatch)
    leak = f'raw https://api.weixin.qq.com/x?access_token={token}'
    wechat = _FakeWechat(response=_json_response({'errcode': errcode, 'errmsg': leak}))
    wechat.install(monkeypatch)

    with pytest.raises(errors.GatewayError) as exc_info:
        _call(op, SimpleNamespace())

    msg = exc_info.value.msg
    assert fragment in msg
    assert token not in msg
    assert 'errmsg' not in msg
    assert 'api.weixin.qq.com' not in msg
    assert redis.set_calls == []


def test_non_200_supplier_response_is_not_success(
    clock: _Clock, monkeypatch: pytest.MonkeyPatch, token: str
) -> None:
    _patch_dao(monkeypatch, _context(deadline=clock.value + timedelta(hours=2)))
    redis = _patch_redis(monkeypatch)
    leak = f'raw {token}'
    wechat = _FakeWechat(response=_json_response({'errcode': 0, 'errmsg': leak}, status=502))
    wechat.install(monkeypatch)

    with pytest.raises(errors.GatewayError) as exc_info:
        _call('short', SimpleNamespace())

    assert token not in exc_info.value.msg
    assert 'errmsg' not in exc_info.value.msg
    assert redis.set_calls == []


@pytest.mark.parametrize(
    'response',
    [
        _json_response({'errcode': 40165, 'errmsg': 'raw'}),
        _json_response([]),
        _json_response({'errcode': 0, 'errmsg': 'ok'}),
        _raw_response(b'{broken', 'application/json'),
        _raw_response(b'not-image', 'text/plain'),
        _image_response(b'', 'image/png'),
    ],
)
def test_invalid_qrcode_supplier_responses_are_rejected(
    clock: _Clock, monkeypatch: pytest.MonkeyPatch, token: str, response: httpx.Response
) -> None:
    _patch_dao(monkeypatch, _context(deadline=clock.value + timedelta(hours=2)))
    redis = _patch_redis(monkeypatch)
    wechat = _FakeWechat(response=response)
    wechat.install(monkeypatch)

    with pytest.raises(errors.GatewayError) as exc_info:
        _call('qrcode', SimpleNamespace())

    assert token not in exc_info.value.msg
    assert len(wechat.requests) == 1
    assert redis.set_calls == []


INVALID_LINKS = [
    ('short', {}),
    ('short', {'link': ''}),
    ('short', {'link': None}),
    ('short', {'link': 12}),
    ('short', {'link': 'https://wxaurl.cn/Invite'}),
    ('short', {'link': '#小程序://'}),
    ('short', {'link': '小程序://Invite'}),
    ('short', {'link': '#小程序://Invite\r\nInjected: value'}),
    ('short', {'link': '#小程序://Invite\x00'}),
    ('short', {'link': '#小程序://' + 'a' * 2049}),
    ('short', []),
    ('url', {}),
    ('url', {'url_link': ''}),
    ('url', {'url_link': None}),
    ('url', {'url_link': 12}),
    ('url', {'url_link': 'http://wxaurl.cn/Invite'}),
    ('url', {'url_link': 'https://evil.example/Invite'}),
    ('url', {'url_link': 'https://wxaurl.cn.evil.example/Invite'}),
    ('url', {'url_link': 'https://wxaurl.cn'}),
    ('url', {'url_link': 'https://wxaurl.cn/'}),
    ('url', {'url_link': 'https://wxaurl.cn/Invite\r\nInjected: value'}),
    ('url', {'url_link': 'https://wxaurl.cn/Invite\x00'}),
    ('url', {'url_link': 'https://wxaurl.cn/' + 'a' * 2049}),
    ('url', []),
]


@pytest.mark.parametrize(['kind', 'payload'], INVALID_LINKS)
def test_invalid_supplier_links_are_rejected(
    clock: _Clock, monkeypatch: pytest.MonkeyPatch, token: str, kind: str, payload: object
) -> None:
    _patch_dao(monkeypatch, _context(deadline=clock.value + timedelta(hours=2)))
    redis = _patch_redis(monkeypatch)
    wechat = _FakeWechat(response=_json_response(payload))
    wechat.install(monkeypatch)

    with pytest.raises(errors.GatewayError) as exc_info:
        _call(kind, SimpleNamespace())

    assert '邀请链接无效' in exc_info.value.msg
    assert token not in exc_info.value.msg
    assert len(wechat.requests) == 1
    assert redis.set_calls == []


def _find_route(path: str) -> APIRoute:
    for route in group_buy_api.router.routes:
        if isinstance(route, APIRoute) and route.path == path:
            return route
    raise AssertionError(f'route not found: {path}')


def _has_jwt(route: APIRoute) -> bool:
    return DependsJwtAuth in route.dependencies


def test_share_routes_keep_jwt_literal_params_and_response_schemas() -> None:
    qrcode = _find_route('/group-buy/teams/{share_code}/qrcode')
    share_link = _find_route('/group-buy/teams/{share_code}/share-link')

    for route in (qrcode, share_link):
        assert route.methods == {'GET'}
        assert _has_jwt(route)

    assert qrcode.endpoint.__annotations__['style'] == Literal['miniapp', 'square']
    assert inspect.signature(qrcode.endpoint).parameters['style'].default == 'miniapp'
    assert share_link.endpoint.__annotations__['kind'] == Literal['short', 'url']
    assert inspect.signature(share_link.endpoint).parameters['kind'].default == 'short'
    assert 'GroupBuyShareCodeResult' in str(qrcode.response_model)
    assert 'GroupBuyShareLinkResult' in str(share_link.response_model)
    assert set(GroupBuyShareCodeResult.model_fields) == {
        'data_url',
        'share_code',
        'deadline',
        'style',
        'env_version',
    }
    assert set(GroupBuyShareLinkResult.model_fields) == {
        'link',
        'kind',
        'share_code',
        'deadline',
        'expires_at',
    }


def test_share_result_schemas_reject_unknown_literals(clock: _Clock) -> None:
    with pytest.raises(ValidationError):
        GroupBuyShareCodeResult(
            data_url='data:image/png;base64,AA==',
            share_code=CODE,
            deadline=clock.value,
            style='bad',
            env_version='trial',
        )
    with pytest.raises(ValidationError):
        GroupBuyShareLinkResult(
            link='https://wxaurl.cn/Invite',
            kind='bad',
            share_code=CODE,
            deadline=clock.value,
            expires_at=clock.value,
        )


def test_share_context_reads_only_eligibility_columns_for_requesting_user(clock: _Clock) -> None:
    row = {
        'status': 'forming',
        'deadline': clock.value + timedelta(hours=2),
        'snapshot': {'base': {'name': '套餐'}},
        'member_status': 'paid',
    }
    db = SimpleNamespace(execute=AsyncMock(return_value=_ExecuteResult(row)))

    data = asyncio.run(group_buy_dao.share_context(db, CODE, USER_ID))

    assert data == row
    stmt = db.execute.await_args.args[0]
    assert list(stmt.selected_columns.keys()) == ['status', 'deadline', 'snapshot', 'member_status']
    assert 'order_id' not in stmt.selected_columns
    assert 'user_id' not in stmt.selected_columns
    compiled = stmt.compile(dialect=postgresql.dialect())
    sql = str(compiled).lower()
    assert 'left outer join pay_group_buy_member' in sql
    assert 'pay_group_buy_member.team_id = pay_group_buy_team.id' in sql
    assert 'pay_group_buy_member.user_id =' in sql
    assert 'pay_group_buy_team.share_code =' in sql
    assert USER_ID in compiled.params.values()
    assert CODE in compiled.params.values()


def test_share_context_returns_none_when_team_is_missing() -> None:
    db = SimpleNamespace(execute=AsyncMock(return_value=_ExecuteResult(None)))

    assert asyncio.run(group_buy_dao.share_context(db, CODE, USER_ID)) is None
