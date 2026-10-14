"""Real route/middleware integration without startup, database, Redis or outbound requests."""

from __future__ import annotations

import asyncio
import socket

from typing import TYPE_CHECKING

import pytest
import redis

from fastapi.testclient import TestClient
from redis import asyncio as async_redis
from sqlalchemy.engine import Engine
from starlette.requests import Request

from backend.common.dataclasses import IpInfo
from backend.core.conf import settings
from backend.middleware.jwt_auth_middleware import JwtAuthMiddleware
from backend.utils.request_parse import get_request_ip

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture(scope='module')
def main_client() -> Iterator[TestClient]:
    original_connect = socket.socket.connect

    def deny_service(*_args: object, **_kwargs: object) -> None:
        raise AssertionError('计算练习测试不允许访问外部服务')

    async def deny_async_service(*_args: object, **_kwargs: object) -> None:  # noqa: RUF029 - async test double
        deny_service()

    async def local_ip_info(request: Request) -> IpInfo:  # noqa: RUF029 - async test double
        # IP metadata is unrelated to route/auth behavior. Even IP_LOCATION_PARSE=false
        # still reads Redis, so isolate the middleware helper rather than that setting.
        return IpInfo(ip=get_request_ip(request), country=None, region=None, city=None)

    def deny_remote_connect(sock: socket.socket, address: tuple) -> None:
        # Windows asyncio uses loopback sockets for its internal wakeup pipe.
        if address[0] in {'127.0.0.1', '::1'}:
            original_connect(sock, address)
            return
        raise AssertionError('计算练习测试不允许访问外部服务')

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(socket.socket, 'connect', deny_remote_connect)
        patch.setattr(socket.socket, 'connect_ex', deny_service)
        # Windows Proactor connects do not go through socket.socket.connect.
        patch.setattr(asyncio.BaseEventLoop, 'create_connection', deny_async_service)
        patch.setattr(redis.Redis, 'execute_command', deny_service)
        patch.setattr(redis.ConnectionPool, 'get_connection', deny_service)
        patch.setattr(async_redis.Redis, 'execute_command', deny_async_service)
        patch.setattr(async_redis.ConnectionPool, 'get_connection', deny_async_service)
        patch.setattr(async_redis.BlockingConnectionPool, 'get_connection', deny_async_service)
        patch.setattr(Engine, 'connect', deny_service)
        from backend.database.redis import RedisCli
        from backend.middleware import state_middleware

        patch.setattr(RedisCli, 'init', deny_async_service)
        patch.setattr(state_middleware, 'parse_ip_info', local_ip_info)
        # Plugin discovery itself writes to Redis before lifespan. Isolate that
        # registry, retaining the real main/builtin routers and all middleware.
        from backend.core import registrar
        from backend.plugin import core as plugin_core

        patch.setattr(plugin_core, 'parse_plugin_config', lambda: ([], []))
        patch.setattr(registrar, 'register_plugin_hooks', lambda _app: None)
        patch.setattr(settings, 'GRAFANA_METRICS_ENABLE', False)
        from backend.core.registrar import register_app

        # No TestClient context manager: deliberately do not enter application lifespan.
        client = TestClient(register_app())
        try:
            yield client
        finally:
            client.close()


@pytest.mark.parametrize('authorization', [None, 'Bearer stale-invalid-token'])
@pytest.mark.parametrize('endpoint', ['catalog', 'basic', 'fill-blank', 'data-practice', 'advanced'])
def test_main_application_public_calculation(
    main_client: TestClient,
    endpoint: str,
    authorization: str | None,
) -> None:
    prefix = f'{settings.FASTAPI_API_V1_PATH}/gk/calculation-practice'
    headers = {'Authorization': authorization} if authorization else {}
    response = (
        main_client.get(f'{prefix}/catalog', headers=headers)
        if endpoint == 'catalog'
        else main_client.post(f'{prefix}/{endpoint}/generate', json={'count': 2, 'seed': 0}, headers=headers)
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload['code'] == 200
    if endpoint != 'catalog':
        assert payload['data']['seed'] == 0
        assert len(payload['data']['questions']) == payload['data']['count'] == 2


@pytest.mark.parametrize(
    'suffix',
    [
        '/gk/calculation-practice/private',
        '/gk/calculation-practice/basic/generate/private',
        '/gk/calculation-practice/catalog/private',
        '/gk/calculation-practice/unknown/generate',
        '/gk/other',
        '/qbank-v2/evaluations/agents/1',
        '/agent/shenlun/runs/1',
    ],
)
def test_public_paths_do_not_widen_auth_exclusions(suffix: str) -> None:
    request = Request({
        'type': 'http',
        'path': f'{settings.FASTAPI_API_V1_PATH}{suffix}',
        'headers': [(b'authorization', b'Bearer still-required')],
    })
    assert JwtAuthMiddleware.extract_token(request) == 'still-required'
