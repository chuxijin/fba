# -*- coding: utf-8 -*-
"""微信扫码登录隔离单元测试：全程 mock 数据库/Redis/微信网关，不连接真实服务。"""

import asyncio
import base64
import hashlib
import inspect
import json
import re

from types import SimpleNamespace
from typing import Any, Self
from unittest.mock import AsyncMock

import httpx
import pytest

import backend.plugin.oauth2.service.wechat_scan_service as scan_module
import backend.utils.wechat_code as wechat_code_module

from backend.common.exception import errors
from backend.common.security.client import LoginClientType, refresh_cookie_key
from backend.plugin.oauth2.api.v1 import wechat as wechat_api
from backend.plugin.oauth2.service.wechat_scan_service import (
    DEFAULT_EXPIRES_SECONDS,
    SCAN_REDIS_PREFIX,
    WechatScanService,
)

PAGE = 'pages/mine/index'
SCENE = 'fba_0123456789abcdef'
DATA_URL = 'data:image/png;base64,AAAA'
PNG_BYTES = b'\x89PNG\r\n\x1a\nscan-login'
SCENE_RE = re.compile(r'^fba_[0-9a-f]{16}$')


class _FakeLock:
    def __init__(self, redis: '_FakeRedis') -> None:
        self._redis = redis
        self._held = False

    async def __aenter__(self) -> Self:
        await self._redis.guard.acquire()
        self._held = True
        return self

    async def __aexit__(self, *_exc: object) -> bool:
        if self._held:
            self._held = False
            self._redis.guard.release()
        return False


class _FakeRedis:
    def __init__(self, *, initial: dict[str, str] | None = None) -> None:
        self.data = dict(initial or {})
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

    async def getdel(self, key: str) -> str | None:
        return self.data.pop(key, None)

    def lock(self, name: str, *, timeout: int | None = None, blocking_timeout: int | None = None) -> _FakeLock:
        self.locks.append((name, timeout, blocking_timeout))
        return _FakeLock(self)


class _FakeUser:
    def model_dump(self, *, mode: str = 'python', include: set[str] | None = None) -> dict[str, object]:
        data = {'id': 7, 'username': 'wx_user', 'nickname': '扫码用户', 'avatar': None}
        if include is None:
            return data
        return {key: value for key, value in data.items() if key in include}


class _FakeTokenInfo:
    client_type = LoginClientType.extension

    def __init__(self) -> None:
        self.user = _FakeUser()

    def model_dump(self, *, mode: str = 'python') -> dict[str, object]:
        return {
            'access_token': 'access-token',
            'client_type': self.client_type.value,
            'user': self.user.model_dump(mode=mode, include={'id', 'username', 'nickname', 'avatar'}),
        }


def _patch_redis(monkeypatch: pytest.MonkeyPatch, *, initial: dict[str, str] | None = None) -> _FakeRedis:
    fake = _FakeRedis(initial=initial)
    monkeypatch.setattr(scan_module, 'redis_client', fake)
    monkeypatch.setattr(wechat_code_module, 'redis_client', fake)
    return fake


def _install_http(monkeypatch: pytest.MonkeyPatch, handler: Any) -> list[httpx.Request]:
    requests: list[httpx.Request] = []

    def recording(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return handler(request)

    real_client = httpx.AsyncClient
    transport = httpx.MockTransport(recording)

    def factory(*args: Any, **kwargs: Any) -> httpx.AsyncClient:
        kwargs['transport'] = transport
        return real_client(*args, **kwargs)

    monkeypatch.setattr(wechat_code_module.httpx, 'AsyncClient', factory)
    return requests


def _code_cache_key(*, version: str, page: str = PAGE, scene: str = SCENE) -> str:
    identity = hashlib.sha256(f'{version}:{page}:{scene}'.encode()).hexdigest()
    return f'miniapp:share-code:{identity}'


# ---------------------------------------------------------------------------
# generate_scan_qrcode：只走共享微信工具，失败绝不落地可轮询的假场景
# ---------------------------------------------------------------------------


async def test_generate_scan_qrcode_delegates_to_shared_helper_and_stores_pending(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _patch_redis(monkeypatch)
    monkeypatch.setattr(
        scan_module,
        'ctx',
        SimpleNamespace(ip='1.2.3.4', os='macOS', browser='Chrome', device='desktop'),
    )
    helper = AsyncMock(return_value=DATA_URL)
    monkeypatch.setattr(wechat_code_module, 'create_miniapp_code', helper)

    result = await WechatScanService.generate_scan_qrcode()

    assert SCENE_RE.match(result['scene_id']), result['scene_id']
    assert result['expires_in'] == DEFAULT_EXPIRES_SECONDS
    assert result['qrcode_data_url'] == DATA_URL
    helper.assert_awaited_once_with(page=PAGE, scene=result['scene_id'], ttl=DEFAULT_EXPIRES_SECONDS)

    key, payload, ttl = fake.set_calls[0]
    assert key == f'{SCAN_REDIS_PREFIX}{result["scene_id"]}'
    assert ttl == DEFAULT_EXPIRES_SECONDS
    assert json.loads(payload) == {
        'status': 'PENDING',
        'client_type': 'web',
        'session_info': {'ip': '1.2.3.4', 'os': 'macOS', 'browser': 'Chrome', 'device': 'desktop'},
    }


@pytest.mark.parametrize('page', [PAGE, 'pkg/mine/scan/index'])
async def test_generate_scan_qrcode_passes_page_through_to_helper(monkeypatch: pytest.MonkeyPatch, page: str) -> None:
    _patch_redis(monkeypatch)
    monkeypatch.setattr(scan_module, 'ctx', SimpleNamespace(ip=None, os=None, browser=None, device=None))
    helper = AsyncMock(return_value=DATA_URL)
    monkeypatch.setattr(wechat_code_module, 'create_miniapp_code', helper)

    result = await WechatScanService.generate_scan_qrcode(page=page)

    assert helper.await_args.kwargs['page'] == page
    assert result['qrcode_data_url'] == DATA_URL


@pytest.mark.parametrize('client_type', [LoginClientType.web, LoginClientType.extension, LoginClientType.admin])
async def test_generate_scan_qrcode_keeps_target_client_in_scene(
    monkeypatch: pytest.MonkeyPatch, client_type: LoginClientType
) -> None:
    fake = _patch_redis(monkeypatch)
    monkeypatch.setattr(scan_module, 'ctx', SimpleNamespace(ip=None, os=None, browser=None, device=None))
    monkeypatch.setattr(wechat_code_module, 'create_miniapp_code', AsyncMock(return_value=DATA_URL))

    await WechatScanService.generate_scan_qrcode(client_type=client_type)

    state = json.loads(fake.set_calls[0][1])
    assert state['client_type'] == client_type.value
    assert state['status'] == 'PENDING'


async def test_generate_scan_qrcode_rejects_miniapp_client_before_helper_or_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _patch_redis(monkeypatch)
    helper = AsyncMock(return_value=DATA_URL)
    monkeypatch.setattr(wechat_code_module, 'create_miniapp_code', helper)

    with pytest.raises(errors.RequestError, match='不支持电脑扫码登录'):
        await WechatScanService.generate_scan_qrcode(client_type=LoginClientType.miniapp)

    helper.assert_not_awaited()
    assert fake.set_calls == []


async def test_generate_scan_qrcode_failure_writes_no_pending_and_returns_no_fake_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _patch_redis(monkeypatch)
    monkeypatch.setattr(scan_module, 'ctx', SimpleNamespace(ip=None, os=None, browser=None, device=None))
    helper = AsyncMock(side_effect=errors.GatewayError(msg='小程序码生成失败，请确认页面已上传到对应微信版本'))
    monkeypatch.setattr(wechat_code_module, 'create_miniapp_code', helper)

    with pytest.raises(errors.GatewayError, match='小程序码生成失败'):
        await WechatScanService.generate_scan_qrcode()

    helper.assert_awaited_once()
    # 失败时既不能写入 PENDING，也不能返回任何可轮询的替代图片（例如旧 SVG 兜底）。
    assert fake.set_calls == []
    assert fake.data == {}


def test_scan_qrcode_api_and_service_default_to_mine_page() -> None:
    assert inspect.signature(wechat_api.get_scan_qrcode).parameters['page'].default == PAGE
    assert inspect.signature(WechatScanService.generate_scan_qrcode).parameters['page'].default == PAGE


# ---------------------------------------------------------------------------
# 共享 helper：dev=trial / prod=release，拒绝非图片响应
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ('environment', 'version', 'check_path'),
    [('dev', 'trial', False), ('prod', 'release', True)],
)
def test_create_miniapp_code_shared_helper_selects_environment(
    monkeypatch: pytest.MonkeyPatch,
    environment: str,
    version: str,
    *,
    check_path: bool,
) -> None:
    monkeypatch.setattr(wechat_code_module.settings, 'ENVIRONMENT', environment)
    fake = _patch_redis(monkeypatch)
    get_token = AsyncMock(return_value='access-token')
    monkeypatch.setattr(WechatScanService, 'get_access_token', get_token)
    requests = _install_http(
        monkeypatch,
        lambda _request: httpx.Response(200, content=PNG_BYTES, headers={'content-type': 'image/png'}),
    )

    data_url = asyncio.run(wechat_code_module.create_miniapp_code(page=PAGE, scene=SCENE, ttl=300))

    expected = f'data:image/png;base64,{base64.b64encode(PNG_BYTES).decode()}'
    assert data_url == expected
    assert len(requests) == 1
    request = requests[0]
    assert request.url.path == '/wxa/getwxacodeunlimit'
    assert request.url.params['access_token'] == 'access-token'
    assert json.loads(request.content) == {
        'scene': SCENE,
        'page': PAGE,
        'width': 430,
        'env_version': version,
        'check_path': check_path,
        'auto_color': False,
        'line_color': {'r': 22, 'g': 128, 'b': 96},
    }
    assert fake.set_calls == [(_code_cache_key(version=version), expected, 300)]
    get_token.assert_awaited_once()


def test_create_miniapp_code_reuses_cached_image_without_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(wechat_code_module.settings, 'ENVIRONMENT', 'dev')
    key = _code_cache_key(version='trial')
    fake = _patch_redis(monkeypatch, initial={key: DATA_URL})
    get_token = AsyncMock()
    monkeypatch.setattr(WechatScanService, 'get_access_token', get_token)
    requests = _install_http(monkeypatch, lambda _request: pytest.fail('缓存命中时不得请求微信接口'))

    result = asyncio.run(wechat_code_module.create_miniapp_code(page=PAGE, scene=SCENE, ttl=300))

    assert result == DATA_URL
    assert requests == []
    assert fake.set_calls == []
    get_token.assert_not_awaited()


@pytest.mark.parametrize(
    'response',
    [
        httpx.Response(
            200, content=b'<svg xmlns="http://www.w3.org/2000/svg"/>', headers={'content-type': 'image/svg+xml'}
        ),
        httpx.Response(502, content=PNG_BYTES, headers={'content-type': 'image/png'}),
    ],
)
def test_create_miniapp_code_rejects_non_image_and_does_not_cache(
    monkeypatch: pytest.MonkeyPatch, response: httpx.Response
) -> None:
    monkeypatch.setattr(wechat_code_module.settings, 'ENVIRONMENT', 'dev')
    fake = _patch_redis(monkeypatch)
    monkeypatch.setattr(WechatScanService, 'get_access_token', AsyncMock(return_value='access-token'))
    requests = _install_http(monkeypatch, lambda _request: response)

    with pytest.raises(errors.GatewayError, match='小程序码生成失败'):
        asyncio.run(wechat_code_module.create_miniapp_code(page=PAGE, scene=SCENE, ttl=300))

    assert len(requests) == 1
    assert fake.set_calls == []


# ---------------------------------------------------------------------------
# confirm_scan：按场景保存的目标端签发会话，重复确认不重复授权
# ---------------------------------------------------------------------------


async def test_confirm_scan_issues_session_for_scene_client_type(monkeypatch: pytest.MonkeyPatch) -> None:
    scene_key = f'{SCAN_REDIS_PREFIX}{SCENE}'
    fake = _patch_redis(
        monkeypatch,
        initial={
            scene_key: json.dumps({
                'status': 'PENDING',
                'client_type': 'extension',
                'session_info': {'ip': '1.1.1.1', 'os': 'macOS'},
            })
        },
    )
    login_calls: list[dict[str, Any]] = []

    async def fake_login(**kwargs: Any) -> _FakeTokenInfo:  # noqa: RUF029
        login_calls.append(kwargs)
        kwargs['response'].set_cookie(refresh_cookie_key(kwargs['client_type']), 'refresh-token-value')
        return _FakeTokenInfo()

    monkeypatch.setattr(scan_module.oauth2_service, 'wechat_miniapp_login', fake_login)

    result = await WechatScanService.confirm_scan(
        db=SimpleNamespace(),
        response=SimpleNamespace(),
        background_tasks=None,
        scene_id=SCENE,
        code='js-code',
        nickname='扫码用户',
        avatar='https://avatar.example/u.png',
    )

    assert result is True
    assert len(login_calls) == 1
    call = login_calls[0]
    assert call['client_type'] is LoginClientType.extension
    assert call['session_info'] == {'ip': '1.1.1.1', 'os': 'macOS'}
    assert call['code'] == 'js-code'
    assert call['nickname'] == '扫码用户'
    assert call['avatar'] == 'https://avatar.example/u.png'
    assert fake.locks == [(f'{scene_key}:lock', 60, 10)]

    confirmed = json.loads(fake.data[scene_key])
    assert confirmed['status'] == 'CONFIRMED'
    assert confirmed['client_type'] == 'extension'
    assert confirmed['token']['access_token'] == 'access-token'
    assert confirmed['refresh_token'] == 'refresh-token-value'
    assert confirmed['user'] == {'id': 7, 'username': 'wx_user', 'nickname': '扫码用户', 'avatar': None}


async def test_confirm_scan_returns_confirmed_scene_without_second_authorization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scene_key = f'{SCAN_REDIS_PREFIX}{SCENE}'
    fake = _patch_redis(
        monkeypatch,
        initial={scene_key: json.dumps({'status': 'CONFIRMED', 'client_type': 'web', 'user': {'id': 7}})},
    )
    login = AsyncMock()
    monkeypatch.setattr(scan_module.oauth2_service, 'wechat_miniapp_login', login)

    result = await WechatScanService.confirm_scan(
        db=SimpleNamespace(),
        response=SimpleNamespace(),
        background_tasks=None,
        scene_id=SCENE,
        code='js-code',
    )

    assert result is True
    login.assert_not_awaited()
    assert fake.set_calls == []
