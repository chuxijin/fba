#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio

from types import SimpleNamespace

import pytest

from backend.app.question_bank.cache import bank_cache as bank_cache_module
from backend.app.question_bank.cache.bank_cache import (
    BankSnapshot,
    bank_cache,
    get_bank_snapshot,
    invalidate_bank_snapshots,
)


def run(coro):
    """同步运行协程"""
    return asyncio.new_event_loop().run_until_complete(coro)


class FakeRedis:
    """伪 Redis"""

    def __init__(self) -> None:
        self.store: dict[str, str | bytes] = {}

    async def get(self, key: str):
        return self.store.get(key)

    async def set(self, key: str, value, ex=None) -> None:
        self.store[key] = value

    async def delete(self, *keys: str) -> None:
        for key in keys:
            self.store.pop(key, None)

    async def delete_prefix(self, prefix: str, exclude=None, batch_size: int = 1000) -> None:
        for key in list(self.store.keys()):
            if key.startswith(prefix):
                self.store.pop(key, None)


@pytest.fixture
def fake_redis(monkeypatch: pytest.MonkeyPatch) -> FakeRedis:
    fake = FakeRedis()
    monkeypatch.setattr('backend.common.cache.redis_cache.redis_client', fake)
    return fake


@pytest.fixture(autouse=True)
def reset_bank_cache_inflight() -> None:
    """每个测试前清空 single-flight 与 L1, 避免跨测试污染"""
    bank_cache._in_flight.clear()
    from backend.common.cache.local import local_cache_manager
    local_cache_manager.clear()


def _bank_orm(bank_id: int = 42, **overrides) -> SimpleNamespace:
    """构造伪 ORM bank 实例(满足 from_attributes 取字段)"""
    base = {
        'id': bank_id,
        'cat_id': 100,
        'name': f'bank-{bank_id}',
        'code': f'CODE-{bank_id}',
        'desc': None,
        'year': None,
        'cover_url': None,
        'difficulty': None,
        'bank_type': 1,
        'scene_mask': 1,
        'parent_id': None,
        'sort_order': 0,
        'chapter_source_bank_id': bank_id,
        'status': 1,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_get_bank_snapshot_miss_calls_dao(
    monkeypatch: pytest.MonkeyPatch, fake_redis: FakeRedis
) -> None:
    """缓存 miss 时回源 DAO 并 model_validate 成 Snapshot"""
    calls: list[int] = []

    async def fake_get(_db, bank_id: int):
        calls.append(bank_id)
        return _bank_orm(bank_id)

    monkeypatch.setattr(bank_cache_module.bank_dao, 'get', fake_get)

    snapshot = run(get_bank_snapshot(db=None, bank_id=42))
    assert isinstance(snapshot, BankSnapshot)
    assert snapshot.id == 42
    assert calls == [42]


def test_get_bank_snapshot_hit_skips_dao(
    monkeypatch: pytest.MonkeyPatch, fake_redis: FakeRedis
) -> None:
    """第二次调用走缓存, DAO 不应再次被调用"""
    calls: list[int] = []

    async def fake_get(_db, bank_id: int):
        calls.append(bank_id)
        return _bank_orm(bank_id)

    monkeypatch.setattr(bank_cache_module.bank_dao, 'get', fake_get)

    run(get_bank_snapshot(db=None, bank_id=42))
    run(get_bank_snapshot(db=None, bank_id=42))
    assert calls == [42]


def test_invalidate_bank_snapshots_clears_cache(
    monkeypatch: pytest.MonkeyPatch, fake_redis: FakeRedis
) -> None:
    """失效后下次读必须 miss → 重新打 DAO"""
    calls: list[int] = []

    async def fake_get(_db, bank_id: int):
        calls.append(bank_id)
        return _bank_orm(bank_id)

    monkeypatch.setattr(bank_cache_module.bank_dao, 'get', fake_get)

    run(get_bank_snapshot(db=None, bank_id=42))
    assert calls == [42]
    run(invalidate_bank_snapshots([42]))
    run(get_bank_snapshot(db=None, bank_id=42))
    assert calls == [42, 42]


def test_get_bank_snapshot_dao_returns_none_propagates(
    monkeypatch: pytest.MonkeyPatch, fake_redis: FakeRedis
) -> None:
    """DAO 返回 None 时不应被缓存(避免缓存"不存在")"""

    async def fake_get(_db, _bank_id: int):
        return None

    monkeypatch.setattr(bank_cache_module.bank_dao, 'get', fake_get)
    result = run(get_bank_snapshot(db=None, bank_id=999))
    assert result is None
    assert fake_redis.store == {}


def test_bank_snapshot_excludes_volatile_fields() -> None:
    """BankSnapshot 不应包含可变字段, 避免缓存与 DB 漂移"""
    fields = set(BankSnapshot.model_fields.keys())
    volatile = {'q_count_cache', 'total_score_cache', 'buy_count'}
    assert volatile.isdisjoint(fields)


def test_concurrent_get_dedups_via_single_flight(
    monkeypatch: pytest.MonkeyPatch, fake_redis: FakeRedis
) -> None:
    """50 并发 miss 同一 bank → DAO 只调一次"""
    calls = 0

    async def fake_get(_db, bank_id: int):
        nonlocal calls
        await asyncio.sleep(0.005)
        calls += 1
        return _bank_orm(bank_id)

    monkeypatch.setattr(bank_cache_module.bank_dao, 'get', fake_get)

    async def runner():
        return await asyncio.gather(*(get_bank_snapshot(db=None, bank_id=7) for _ in range(50)))

    results = run(runner())
    assert calls == 1
    assert all(r.id == 7 for r in results)
