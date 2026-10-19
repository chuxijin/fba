"""验证 Redis 独立超时配置及订阅长连接的显式覆盖。"""

import json
import os
import subprocess
import sys

from pathlib import Path

from backend.database.redis import RedisCli


def test_environment_timeouts_are_passed_to_the_connection_pool() -> None:
    env = {
        **os.environ,
        'REDIS_SOCKET_TIMEOUT': '13',
        'REDIS_CONNECT_TIMEOUT': '17',
        'REDIS_TIMEOUT': '1',
    }
    result = subprocess.run(
        [sys.executable, '-c', (
            'import json; from backend.database.redis import RedisCli; '
            'kwargs = RedisCli().connection_pool.connection_kwargs; '
            'print(json.dumps({name: kwargs[name] for name in ("socket_timeout", "socket_connect_timeout")}))'
        )],
        cwd=Path(__file__).resolve().parents[3],
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=30,
    )
    assert json.loads(result.stdout) == {'socket_timeout': 13, 'socket_connect_timeout': 17}


def test_explicit_socket_timeout_none_preserves_long_lived_subscriptions() -> None:
    client = RedisCli(socket_timeout=None, socket_connect_timeout=2)
    kwargs = client.connection_pool.connection_kwargs
    assert kwargs['socket_timeout'] is None
    assert kwargs['socket_connect_timeout'] == 2
