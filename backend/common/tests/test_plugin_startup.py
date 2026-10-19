"""插件启动的批量缓存读写、状态保留和失败清理回归。"""

import json

from copy import deepcopy
from typing import Any

import pytest

from redis.exceptions import TimeoutError

from backend.common.enums import PluginLevelType
from backend.core.conf import settings
from backend.plugin import core
from backend.plugin.errors import PluginConfigError


class FakeRedis:
    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.calls: list[tuple[str, Any]] = []
        self.failure: str | None = None

    def record(self, method: str, value: Any = None) -> None:
        self.calls.append((method, value))
        if self.failure == method:
            raise TimeoutError('temporary network timeout')

    async def init(self) -> None:
        self.record('init')

    async def mget_batched(self, keys: list[str]) -> list[str | None]:
        self.record('mget', keys)
        return [self.store.get(key) for key in keys]

    async def mset(self, mapping: dict[str, str]) -> None:
        self.record('mset', mapping)
        self.store.update(mapping)

    async def delete_by_prefix(self, prefix: str, *, exclude_keys: list[str]) -> None:
        self.record('cleanup', exclude_keys)
        for key in list(self.store):
            if key.startswith(f'{prefix}:') and key not in exclude_keys:
                del self.store[key]

    async def delete(self, key: str) -> None:
        self.record('delete', key)
        self.store.pop(key, None)

    async def aclose(self) -> None:
        self.record('close')


@pytest.fixture
def redis(monkeypatch: pytest.MonkeyPatch) -> FakeRedis:
    client = FakeRedis()
    configs = {
        'extension': {'plugin': {'depends_on': []}, 'app': {'extend': 'admin'}, 'api': {'prefix': '/sample'}},
        'application': {'plugin': {'depends_on': ['extension']}, 'app': {'router': ['v1']}},
        'capability': {'plugin': {'depends_on': []}},
    }
    monkeypatch.setattr(core, 'RedisCli', lambda: client)
    monkeypatch.setattr(core, 'get_plugins', lambda: tuple(configs))
    monkeypatch.setattr(core, 'load_plugin_config', lambda name: deepcopy(configs[name]))
    monkeypatch.setattr(core, 'validate_plugin_config', lambda name, config: {
        'extension': PluginLevelType.extend,
        'application': PluginLevelType.app,
        'capability': PluginLevelType.capability,
    }[name])
    return client


def key(name: str) -> str:
    return f'{settings.PLUGIN_REDIS_PREFIX}:{name}'


def test_parse_reads_and_writes_plugins_in_batches_preserving_disabled_state(redis: FakeRedis) -> None:
    redis.store[key('application')] = json.dumps({'plugin': {'enable': '0'}})
    redis.store[key('uninstalled')] = '{}'
    redis.store[key('changed')] = '1'
    extensions, applications = core.parse_plugin_config()
    assert [entry.name for entry in extensions] == ['extension']
    assert [entry.name for entry in applications] == ['application']
    assert applications[0].depends_on == ['extension']
    assert [method for method, _ in redis.calls] == ['init', 'cleanup', 'mget', 'mset', 'delete', 'close']
    assert json.loads(redis.store[key('application')])['plugin']['enable'] == '0'
    assert json.loads(redis.store[key('extension')])['plugin']['enable'] == '1'
    assert key('capability') in redis.store
    assert key('uninstalled') not in redis.store
    assert key('changed') not in redis.store


def test_enabled_plugins_uses_one_batch_read_and_preserves_default_enable(redis: FakeRedis) -> None:
    redis.store[key('application')] = json.dumps({'plugin': {'enable': '0'}})
    redis.store[key('capability')] = 'invalid cache json'
    assert core.get_enabled_plugins() == {'extension', 'capability'}
    assert [method for method, _ in redis.calls] == ['init', 'mget', 'close']


@pytest.mark.parametrize('operation', ['init', 'mget', 'mset'])
def test_timeout_is_propagated_and_client_is_closed(redis: FakeRedis, operation: str) -> None:
    redis.failure = operation
    with pytest.raises(TimeoutError, match='temporary network timeout'):
        core.parse_plugin_config()
    assert redis.calls[-1][0] == 'close'


def test_invalid_manifest_is_not_written(redis: FakeRedis, monkeypatch: pytest.MonkeyPatch) -> None:
    def validate(name: str, config: dict[str, Any]) -> PluginLevelType:
        if name == 'application':
            raise PluginConfigError('invalid manifest')
        return PluginLevelType.extend

    monkeypatch.setattr(core, 'validate_plugin_config', validate)
    with pytest.raises(PluginConfigError, match='invalid manifest'):
        core.parse_plugin_config()
    assert all(method != 'mset' for method, _ in redis.calls)
    assert redis.calls[-1][0] == 'close'


def test_empty_plugin_directory_does_not_send_empty_mset(redis: FakeRedis, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(core, 'get_plugins', lambda: ())
    assert core.parse_plugin_config() == ([], [])
    assert all(method != 'mset' for method, _ in redis.calls)
    assert redis.calls[-1][0] == 'close'
