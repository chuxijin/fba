#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio

from collections.abc import Coroutine
from dataclasses import dataclass
from typing import Any, Never, TypeVar

import pytest

from pydantic import BaseModel

from backend.common.cache.redis_cache import RedisCache
from backend.common.cache.serializers import (
    DataclassSerializer,
    JsonSerializer,
    PydanticSerializer,
)

T = TypeVar('T')


def run(coro: Coroutine[Any, Any, T]) -> T:
    """同步运行协程, 规避项目缺失 pytest-asyncio 的临时方案"""
    return asyncio.new_event_loop().run_until_complete(coro)


class FakeRedis:
    """伪 Redis 客户端, 仅用于单元测试"""

    def __init__(self) -> None:
        self.store: dict[str, str | bytes] = {}
        self.ttls: dict[str, int] = {}
        self.set_calls = 0
        self.get_calls = 0
        self.delete_calls = 0

    async def get(self, key: str) -> str | bytes | None:
        """读取键值"""
        self.get_calls += 1
        return self.store.get(key)

    async def set(self, key: str, value: str | bytes, ex: int | None = None) -> None:
        """写入键值"""
        self.set_calls += 1
        self.store[key] = value
        if ex is not None:
            self.ttls[key] = ex

    async def ttl(self, key: str) -> int:
        return self.ttls.get(key, -1)

    async def delete(self, *keys: str) -> None:
        """删除键"""
        self.delete_calls += 1
        for key in keys:
            self.store.pop(key, None)
            self.ttls.pop(key, None)

    async def delete_prefix(
        self,
        prefix: str,
        exclude: str | list[str] | None = None,
        batch_size: int = 1000,
    ) -> None:
        """按前缀批量删除"""
        self.delete_calls += 1
        for key in list(self.store.keys()):
            if key.startswith(prefix):
                self.store.pop(key, None)
                self.ttls.pop(key, None)


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> FakeRedis:
    """提供伪 redis_client, 替换全局单例"""
    fake = FakeRedis()
    monkeypatch.setattr('backend.common.cache.redis_cache.redis_client', fake)
    return fake


class SampleModel(BaseModel):
    """测试用 Pydantic 模型"""

    user_id: int
    name: str


@dataclass
class SamplePoint:
    """测试用 dataclass"""

    x: int
    y: int


def test_get_miss_returns_none(fake_redis: FakeRedis) -> None:
    cache = RedisCache(prefix='test:miss', ttl=60, serializer=JsonSerializer())
    assert run(cache.get(1)) is None
    assert fake_redis.get_calls == 1


def test_invalid_configuration_is_rejected() -> None:
    with pytest.raises(ValueError, match='prefix'):
        RedisCache(prefix=' ', ttl=60, serializer=JsonSerializer())
    with pytest.raises(ValueError, match='ttl'):
        RedisCache(prefix='test', ttl=0, serializer=JsonSerializer())
    with pytest.raises(ValueError, match='local=True'):
        RedisCache(
            prefix='test',
            ttl=60,
            serializer=JsonSerializer(),
            invalidate_pubsub=True,
        )


def test_set_and_get_dict(fake_redis: FakeRedis) -> None:
    cache = RedisCache(prefix='test:dict', ttl=60, serializer=JsonSerializer())
    run(cache.set(42, value={'foo': 'bar'}))
    assert 'test:dict:42' in fake_redis.store
    assert run(cache.get(42)) == {'foo': 'bar'}


def test_set_none_skips_redis(fake_redis: FakeRedis) -> None:
    cache = RedisCache(prefix='test:none', ttl=60, serializer=JsonSerializer())
    run(cache.set(1, value=None))
    assert fake_redis.set_calls == 0


def test_compound_key_order_matters(fake_redis: FakeRedis) -> None:
    cache = RedisCache(prefix='test:compound', ttl=60, serializer=JsonSerializer())
    run(cache.set(1, 2, 3, value={'order': 'a'}))
    run(cache.set(3, 2, 1, value={'order': 'b'}))
    assert run(cache.get(1, 2, 3)) == {'order': 'a'}
    assert run(cache.get(3, 2, 1)) == {'order': 'b'}


def test_key_parts_are_escaped_to_prevent_collisions(fake_redis: FakeRedis) -> None:
    cache = RedisCache(prefix='test:key', ttl=60, serializer=JsonSerializer())
    run(cache.set('a:b', 'c', value={'key': 1}))
    run(cache.set('a', 'b:c', value={'key': 2}))
    assert run(cache.get('a:b', 'c')) == {'key': 1}
    assert run(cache.get('a', 'b:c')) == {'key': 2}


def test_pydantic_serializer_roundtrip(fake_redis: FakeRedis) -> None:
    cache = RedisCache(prefix='test:pyd', ttl=60, serializer=PydanticSerializer(SampleModel))
    run(cache.set(1, value=SampleModel(user_id=1, name='alice')))
    got = run(cache.get(1))
    assert isinstance(got, SampleModel)
    assert got.user_id == 1 and got.name == 'alice'


def test_dataclass_serializer_roundtrip(fake_redis: FakeRedis) -> None:
    cache = RedisCache(prefix='test:dc', ttl=60, serializer=DataclassSerializer(SamplePoint))
    run(cache.set(1, value=SamplePoint(x=3, y=4)))
    got = run(cache.get(1))
    assert isinstance(got, SamplePoint) and got.x == 3 and got.y == 4


def test_get_or_set_miss_invokes_factory(fake_redis: FakeRedis) -> None:
    cache = RedisCache(prefix='test:gos', ttl=60, serializer=JsonSerializer())
    calls = 0

    async def factory() -> dict:
        await asyncio.sleep(0)
        nonlocal calls
        calls += 1
        return {'val': 1}

    assert run(cache.get_or_set(1, factory=factory)) == {'val': 1}
    assert calls == 1
    assert run(cache.get_or_set(1, factory=factory)) == {'val': 1}
    assert calls == 1


def test_get_or_set_can_skip_cache(fake_redis: FakeRedis) -> None:
    calls = 0
    cache = RedisCache(prefix='test:condition', ttl=60, serializer=JsonSerializer())

    async def factory() -> dict:
        await asyncio.sleep(0)
        nonlocal calls
        calls += 1
        return {'status': 'draft'}

    assert run(cache.get_or_set(1, factory=factory, should_cache=lambda item: item['status'] == 'published'))
    assert run(cache.get_or_set(1, factory=factory, should_cache=lambda item: item['status'] == 'published'))
    assert calls == 2
    assert fake_redis.set_calls == 0


def test_single_flight_dedup(fake_redis: FakeRedis) -> None:
    """50 个并发 miss 同一 key, factory 只应调用 1 次"""
    cache = RedisCache(prefix='test:sf', ttl=60, serializer=JsonSerializer())
    calls = 0

    async def slow_factory() -> dict:
        nonlocal calls
        await asyncio.sleep(0.01)
        calls += 1
        return {'val': calls}

    async def runner() -> list[dict | None]:
        return await asyncio.gather(*(cache.get_or_set(1, factory=slow_factory) for _ in range(50)))

    results = run(runner())
    assert calls == 1
    assert all(r == {'val': 1} for r in results)


def test_get_or_set_factory_exception_clears_inflight(fake_redis: FakeRedis) -> None:
    cache = RedisCache(prefix='test:err', ttl=60, serializer=JsonSerializer())

    async def boom() -> dict:
        await asyncio.sleep(0)
        raise RuntimeError('oops')

    with pytest.raises(RuntimeError):
        run(cache.get_or_set(1, factory=boom))
    assert cache._in_flight == {}

    async def ok() -> dict:
        await asyncio.sleep(0)
        return {'val': 'ok'}

    assert run(cache.get_or_set(1, factory=ok)) == {'val': 'ok'}


def test_invalidate_removes_key(fake_redis: FakeRedis) -> None:
    cache = RedisCache(prefix='test:inv', ttl=60, serializer=JsonSerializer())
    run(cache.set(1, value={'val': 1}))
    run(cache.invalidate(1))
    assert run(cache.get(1)) is None


def test_invalidate_prefix_removes_all(fake_redis: FakeRedis) -> None:
    cache = RedisCache(prefix='test:invp', ttl=60, serializer=JsonSerializer())
    run(cache.set(1, 'a', value={'val': 'a'}))
    run(cache.set(1, 'b', value={'val': 'b'}))
    run(cache.set(2, 'a', value={'val': 'c'}))
    run(cache.invalidate_prefix(1))
    assert run(cache.get(1, 'a')) is None
    assert run(cache.get(1, 'b')) is None
    assert run(cache.get(2, 'a')) == {'val': 'c'}


def test_invalidate_publishes_with_official_argument(
    monkeypatch: pytest.MonkeyPatch,
    fake_redis: FakeRedis,
) -> None:
    messages: list[tuple[str, bool]] = []

    async def publish(cache_key: str, *, delete_by_prefix: bool) -> None:
        await asyncio.sleep(0)
        messages.append((cache_key, delete_by_prefix))

    monkeypatch.setattr(
        'backend.common.cache.redis_cache.cache_pubsub_manager.publish_invalidation',
        publish,
    )
    cache = RedisCache(
        prefix='test:pubsub',
        ttl=60,
        serializer=JsonSerializer(),
        local=True,
        invalidate_pubsub=True,
    )
    run(cache.invalidate(1))
    run(cache.invalidate_prefix())
    assert messages == [('test:pubsub:1', False), ('test:pubsub', True)]


def test_redis_get_failure_returns_none(monkeypatch: pytest.MonkeyPatch, fake_redis: FakeRedis) -> None:
    async def boom(*_a: Any, **_kw: Any) -> Never:
        await asyncio.sleep(0)
        raise ConnectionError('redis down')

    monkeypatch.setattr(fake_redis, 'get', boom)
    cache = RedisCache(prefix='test:fail', ttl=60, serializer=JsonSerializer())
    assert run(cache.get(1)) is None


def test_redis_set_failure_silently_skips(monkeypatch: pytest.MonkeyPatch, fake_redis: FakeRedis) -> None:
    async def boom(*_a: Any, **_kw: Any) -> Never:
        await asyncio.sleep(0)
        raise ConnectionError('redis down')

    monkeypatch.setattr(fake_redis, 'set', boom)
    cache = RedisCache(prefix='test:failset', ttl=60, serializer=JsonSerializer())
    run(cache.set(1, value={'x': 1}))


def test_corrupt_payload_is_deleted(fake_redis: FakeRedis) -> None:
    fake_redis.store['test:corrupt:1'] = b'not-json'
    cache = RedisCache(prefix='test:corrupt', ttl=60, serializer=JsonSerializer())
    assert run(cache.get(1)) is None
    assert 'test:corrupt:1' not in fake_redis.store
