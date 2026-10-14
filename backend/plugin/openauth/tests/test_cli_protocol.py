"""实际 Node CLI 对接真实 FastAPI 路由；身份、数据库、Redis 均为隔离测试桩。"""

# ruff: noqa: ANN001, ANN201, ANN202, RUF029
import json
import shutil
import socket
import subprocess
import threading
import time

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import uvicorn

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.common.exception import errors
from backend.common.security.jwt import jwt_authentication_verify
from backend.core.conf import settings
from backend.database.db import get_db, get_db_transaction
from backend.plugin.openauth.api.router import v1
from backend.plugin.openauth.tests.test_authorization_service import env as authorization_env
from backend.plugin.openauth.tests.test_profile import profile

env = authorization_env


def test_real_cli_against_fastapi_protocol(env, tmp_path, monkeypatch):
    node = shutil.which('node')
    if not node:
        pytest.skip('Node.js required for CLI protocol integration')
    cli = Path(__file__).resolve().parents[4] / 'skills/youanshang/scripts/youanshang.cjs'
    app = FastAPI()
    app.include_router(v1)

    async def session():
        yield None

    def test_login(request: Request):
        request.scope['user'] = SimpleNamespace(id=100)
        return 'test-only-login'

    @app.exception_handler(errors.BaseExceptionError)
    async def domain_error(request, exc):
        return JSONResponse(status_code=exc.code, content={'code': exc.code, 'msg': exc.msg})

    app.dependency_overrides[get_db] = session
    app.dependency_overrides[get_db_transaction] = session
    app.dependency_overrides[jwt_authentication_verify] = test_login
    monkeypatch.setattr(
        profile,
        'get_current_user',
        AsyncMock(
            return_value=SimpleNamespace(
                id=100,
                nickname='CLI protocol test',
                avatar=None,
            )
        ),
    )
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level='error', access_log=False))
    thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
    thread.start()
    try:
        deadline = time.monotonic() + 10
        while not server.started and time.monotonic() < deadline:
            time.sleep(0.01)
        assert server.started
        api = f'http://127.0.0.1:{port}{settings.FASTAPI_API_V1_PATH}/openauth'

        def command(*args):
            result = subprocess.run(
                [node, str(cli), *args, '--config-dir', str(tmp_path / 'cli')],
                capture_output=True,
                text=True,
                encoding='utf-8',
                timeout=30,
                check=False,
            )
            assert result.returncode == 0, result.stdout
            return [json.loads(line) for line in result.stdout.splitlines()]

        command(
            'configure',
            '--api-base-url',
            api,
            '--authorize-url',
            f'http://127.0.0.1:{port}/authorize',
            '--client-id',
            env.client.client_id,
        )
        events = command('login', '--manual')
        query = parse_qs(urlsplit(events[0]['url']).query)
        # 只对隔离测试账号模拟明确确认；不使用真实用户登录态或浏览器自动点击。
        authorization = httpx.post(
            f'{api}/authorize',
            json={
                'client_id': query['client_id'][0],
                'scopes': query['scope'][0].split(),
                'redirect_uri': query['redirect_uri'][0],
                'state': query['state'][0],
                'code_challenge': query['code_challenge'][0],
                'code_challenge_method': 'S256',
            },
            timeout=10,
        )
        assert authorization.status_code == 200
        data = authorization.json()['data']
        assert command('login', '--token', data['code'])[0]['data']['authorized']
        assert command('check')[0]['data']['scopes'] == ['profile:read']
        assert (
            command('get-user-info', '--session-input', '查看账号', '--session-id', '1784035443-a1b2c3')[0]['data'][
                'nickname'
            ]
            == 'CLI protocol test'
        )
        # 强制测试配置中的访问令牌过期，让实际 CLI 发起一次旋转刷新。
        state_file = tmp_path / 'cli/state.json'
        state = json.loads(state_file.read_text(encoding='utf-8'))
        previous_refresh = state['tokens']['refresh_token']
        state['tokens']['expires_at'] = 1
        state_file.write_text(json.dumps(state), encoding='utf-8')
        assert command('profile')[0]['data']['user_id'] == 100
        state = json.loads(state_file.read_text(encoding='utf-8'))
        assert previous_refresh != state['tokens']['refresh_token']
        assert command('logout')[0]['data']['remote_revocation_confirmed']
        assert not command('status')[0]['data']['authorized']
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()
        assert not thread.is_alive()
