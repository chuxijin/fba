import asyncio

from time import time
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from sqlalchemy import Column, Integer, MetaData, Table, create_engine, insert, update
from sqlalchemy.orm import Session, registry

from backend.app.question_bank_v2.cache import knowledge_invalidation as invalidation
from backend.app.question_bank_v2.cache import public_knowledge_cache as cache_module
from backend.app.question_bank_v2.cache.public_knowledge_cache import PUBLISH, PublicKnowledgeCache
from backend.app.question_bank_v2.schema.knowledge import GetKnowledgePointNode, KnowledgePublicSnapshot
from backend.app.question_bank_v2.service import knowledge_service as service_module
from backend.app.question_bank_v2.service.knowledge_service import KnowledgeService
from backend.common.exception import errors


class MemoryRedis:
    def __init__(self) -> None:
        self.data: dict[str, tuple[Any, float]] = {}

    async def get(self, key: str) -> Any:
        item = self.data.get(key)
        return item[0] if item and item[1] > time() else None

    async def set(self, key: str, value: Any, *, nx: bool = False, ex: int | None = None) -> bool:
        if nx and await self.get(key) is not None:
            return False
        self.data[key] = (value, time() + ex if ex is not None else float('inf'))
        return True

    async def eval(self, script: str, _count: int, *args: Any) -> int:
        if script == PUBLISH:
            lock, generation_key, key, token, generation, raw, ttl = args
            if await self.get(lock) != token or (await self.get(generation_key) or '0') != generation:
                return 0
            await self.set(key, raw, ex=ttl)
            return 1
        key, token = args
        if await self.get(key) == token:
            self.data.pop(key, None)
            return 1
        return 0


def snapshot(count: int = 10, *, fresh: bool = True) -> KnowledgePublicSnapshot:
    return KnowledgePublicSnapshot(
        points=[GetKnowledgePointNode(id=1, system_id=3, code='root', name='根', depth=0, sort_order=0)],
        counts={1: {'question_count': count, 'direct_question_count': count}},
        fresh_until=time() + 300 if fresh else 0,
    )


@pytest.fixture
def redis(monkeypatch: pytest.MonkeyPatch) -> MemoryRedis:
    redis = MemoryRedis()
    monkeypatch.setattr(cache_module, 'redis_client', redis)
    return redis


@pytest.mark.asyncio
async def test_concurrent_cold_requests_across_instances_have_one_factory(redis: MemoryRedis) -> None:
    caches = [PublicKnowledgeCache(), PublicKnowledgeCache()]
    calls = 0
    gate = asyncio.Event()

    async def factory() -> KnowledgePublicSnapshot:
        nonlocal calls
        calls += 1
        await gate.wait()
        return snapshot()

    requests = [asyncio.create_task(caches[i % 2].get(3, 1, None, factory=factory)) for i in range(20)]
    await asyncio.sleep(0.02)
    assert calls == 1
    gate.set()
    results = await asyncio.gather(*requests)
    assert len(results) == 20
    assert calls == 1
    assert all(item.counts[1]['question_count'] == 10 for item in results)
    assert not any(key.endswith(':lock') for key in redis.data)


@pytest.mark.asyncio
async def test_stale_value_returns_immediately_and_refreshes_independently(redis: MemoryRedis) -> None:
    caches = [PublicKnowledgeCache(), PublicKnowledgeCache()]
    gate = asyncio.Event()
    factory = AsyncMock(return_value=snapshot(20))
    key = f'{cache_module.PREFIX}:0:3:1:0'
    await redis.set(key, snapshot(fresh=False).model_dump_json(), ex=1800)

    async def blocked() -> KnowledgePublicSnapshot:
        await gate.wait()
        return await factory()

    results = await asyncio.gather(*(cache.get(3, 1, None, factory=blocked) for cache in caches))
    assert [item.counts[1]['question_count'] for item in results] == [10, 10]
    gate.set()
    tasks = [task for cache in caches for task in cache.tasks.values()]
    await asyncio.gather(*tasks)
    assert factory.await_count == 1
    fresh = await caches[0].get(3, 1, None, factory=blocked)
    assert fresh.counts[1]['question_count'] == 20


@pytest.mark.asyncio
async def test_invalidation_during_refresh_prevents_old_fill(redis: MemoryRedis) -> None:
    cache = PublicKnowledgeCache()
    gate = asyncio.Event()
    started = asyncio.Event()

    async def old_factory() -> KnowledgePublicSnapshot:
        started.set()
        await gate.wait()
        return snapshot(10)

    old = asyncio.create_task(cache.get(3, 1, None, factory=old_factory))
    await started.wait()
    await cache.invalidate()
    gate.set()
    await old
    assert await redis.get(f'{cache_module.PREFIX}:0:3:1:0') is None
    factory = AsyncMock(return_value=snapshot(20))
    assert (await cache.get(3, 1, None, factory=factory)).counts[1]['question_count'] == 20
    factory.assert_awaited_once()


@pytest.mark.asyncio
async def test_scope_keys_separate_root_revision_and_system(redis: MemoryRedis) -> None:
    cache = PublicKnowledgeCache()
    factory = AsyncMock(return_value=snapshot())
    for system, root, revision in [(3, 1, None), (3, 2, None), (3, 1, 11), (4, 1, None)]:
        await cache.get(system, root, revision, factory=factory)
    assert factory.await_count == 4
    await cache.get(3, 1, None, factory=factory)
    assert factory.await_count == 4


@pytest.mark.asyncio
async def test_refresh_failure_retains_stale_value_and_releases_lock(redis: MemoryRedis) -> None:
    cache = PublicKnowledgeCache()
    key = f'{cache_module.PREFIX}:0:3:1:0'
    await redis.set(key, snapshot(fresh=False).model_dump_json(), ex=1800)
    factory = AsyncMock(side_effect=RuntimeError('database unavailable'))
    assert (await cache.get(3, 1, None, factory=factory)).counts[1]['question_count'] == 10
    await asyncio.gather(*cache.tasks.values(), return_exceptions=True)
    assert await redis.get(key) is not None
    assert await redis.get(f'{key}:lock') is None


@pytest.mark.asyncio
async def test_cancelled_waiter_does_not_cancel_shared_refresh(redis: MemoryRedis) -> None:
    cache = PublicKnowledgeCache()
    gate = asyncio.Event()

    async def factory() -> KnowledgePublicSnapshot:
        await gate.wait()
        return snapshot()

    first = asyncio.create_task(cache.get(3, 1, None, factory=factory))
    second = asyncio.create_task(cache.get(3, 1, None, factory=factory))
    await asyncio.sleep(0.01)
    first.cancel()
    with pytest.raises(asyncio.CancelledError):
        await first
    gate.set()
    assert (await second).counts[1]['question_count'] == 10


@pytest.mark.asyncio
async def test_redis_unavailable_combines_local_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cache_module, 'redis_client', AsyncMock(get=AsyncMock(side_effect=OSError('offline'))))
    cache = PublicKnowledgeCache()
    gate = asyncio.Event()
    calls = 0

    async def factory() -> KnowledgePublicSnapshot:
        nonlocal calls
        calls += 1
        await gate.wait()
        return snapshot()

    requests = [asyncio.create_task(cache.get(3, 1, None, factory=factory)) for _ in range(5)]
    await asyncio.sleep(0.01)
    gate.set()
    await asyncio.gather(*requests)
    assert calls == 1


@pytest.mark.asyncio
async def test_corrupt_payload_is_rebuilt(redis: MemoryRedis) -> None:
    cache = PublicKnowledgeCache()
    key = f'{cache_module.PREFIX}:0:3:1:0'
    await redis.set(key, '{corrupt', ex=1800)
    factory = AsyncMock(return_value=snapshot(30))
    assert (await cache.get(3, 1, None, factory=factory)).counts[1]['question_count'] == 30
    assert KnowledgePublicSnapshot.model_validate_json(await redis.get(key)).counts[1]['question_count'] == 30


@pytest.mark.asyncio
async def test_redis_publish_failure_still_returns_computed_data(
    redis: MemoryRedis,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_eval = redis.eval

    async def fail_publish(script: str, count: int, *args: Any) -> int:
        if script == PUBLISH:
            raise OSError('Redis write failed')
        return await original_eval(script, count, *args)

    monkeypatch.setattr(redis, 'eval', fail_publish)
    cache = PublicKnowledgeCache()
    value = await cache.get(3, 1, None, factory=AsyncMock(return_value=snapshot()))
    assert value.counts[1]['question_count'] == 10
    assert not any(key.endswith(':lock') for key in redis.data)


@pytest.mark.asyncio
async def test_busy_cold_lock_has_bounded_wait(redis: MemoryRedis) -> None:
    cache = PublicKnowledgeCache()
    cache.wait_seconds = 0.01
    key = f'{cache_module.PREFIX}:0:3:1:0'
    await redis.set(f'{key}:lock', 'other', ex=15)
    factory = AsyncMock(return_value=snapshot())
    with pytest.raises(errors.ServerError):
        await cache.get(3, 1, None, factory=factory)
    factory.assert_not_awaited()


@pytest.mark.asyncio
async def test_cached_public_snapshot_keeps_user_data_realtime_and_unmodified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    public = snapshot()
    monkeypatch.setattr(service_module.public_knowledge_cache, 'get', AsyncMock(return_value=public))
    monkeypatch.setattr(
        service_module.knowledge_system_dao,
        'get',
        AsyncMock(
            return_value=SimpleNamespace(
                id=3,
                domain_category_id=1,
                code='x',
                name='x',
                version='default',
                status='active',
                description=None,
            )
        ),
    )
    progress = AsyncMock(side_effect=[{1: {'answered_count': 1}}, {1: {'answered_count': 2}}])
    monkeypatch.setattr(service_module.knowledge_point_dao, 'get_user_progress', progress)
    db = SimpleNamespace(bind=None)
    first = await KnowledgeService.get_tree(db=db, user_id=7, system_id=3, root_id=1)
    second = await KnowledgeService.get_tree(db=db, user_id=8, system_id=3, root_id=1)
    assert (first.total_answered_count, second.total_answered_count) == (1, 2)
    assert 'answered_count' not in public.counts[1]
    assert progress.await_args_list[0].kwargs['user_id'] == 7
    assert progress.await_args_list[1].kwargs['user_id'] == 8


@pytest.mark.asyncio
async def test_commit_invalidates_once_and_rollback_does_not(monkeypatch: pytest.MonkeyPatch) -> None:
    factory = AsyncMock()
    monkeypatch.setattr(invalidation.public_knowledge_cache, 'invalidate', factory)
    engine = create_engine('sqlite://')
    table = Table('qbank_v2_bank_item', MetaData(), Column('id', Integer, primary_key=True))
    table.create(engine)
    with Session(engine) as session:
        session.execute(insert(table).values(id=1))
        session.execute(insert(table).values(id=2))
        assert factory.await_count == 0
        session.commit()
        await asyncio.gather(*invalidation.tasks)
        assert factory.await_count == 1
        session.execute(update(table).values(id=3).where(table.c.id == 1))
        session.rollback()
        await asyncio.sleep(0)
        assert factory.await_count == 1
        session.commit()
        assert factory.await_count == 1
    engine.dispose()


@pytest.mark.asyncio
async def test_refresh_timeout_cleans_up_lock(redis: MemoryRedis) -> None:
    cache = PublicKnowledgeCache()
    cache.refresh_seconds = 0.01

    async def factory() -> KnowledgePublicSnapshot:
        await asyncio.Event().wait()
        return snapshot()

    with pytest.raises(TimeoutError):
        await cache.get(3, 1, None, factory=factory)
    assert not any(key.endswith(':lock') for key in redis.data)


@pytest.mark.asyncio
async def test_expired_lock_owner_cannot_overwrite_or_unlock_successor(redis: MemoryRedis) -> None:
    cache = PublicKnowledgeCache()
    key = f'{cache_module.PREFIX}:0:3:1:0'

    async def factory() -> KnowledgePublicSnapshot:
        await redis.set(f'{key}:lock', 'successor', ex=15)
        return snapshot()

    await cache.get(3, 1, None, factory=factory)
    assert await redis.get(key) is None
    assert await redis.get(f'{key}:lock') == 'successor'


@pytest.mark.asyncio
async def test_shutdown_cancels_refresh_and_releases_lock(redis: MemoryRedis) -> None:
    cache = PublicKnowledgeCache()
    started = asyncio.Event()

    async def factory() -> KnowledgePublicSnapshot:
        started.set()
        await asyncio.Event().wait()
        return snapshot()

    request = asyncio.create_task(cache.get(3, 1, None, factory=factory))
    await started.wait()
    await cache.close()
    with pytest.raises(asyncio.CancelledError):
        await request
    assert not cache.tasks
    assert not any(key.endswith(':lock') for key in redis.data)


@pytest.mark.asyncio
async def test_nested_rollback_discards_changes_but_nested_commit_waits_for_outer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = AsyncMock()
    monkeypatch.setattr(invalidation.public_knowledge_cache, 'invalidate', factory)
    engine = create_engine('sqlite://')
    table = Table('qbank_v2_bank_item', MetaData(), Column('id', Integer, primary_key=True))
    table.create(engine)
    with Session(engine) as session:
        with session.begin():
            nested = session.begin_nested()
            session.execute(insert(table).values(id=1))
            nested.rollback()
        assert factory.await_count == 0
        with session.begin():
            with session.begin_nested():
                session.execute(insert(table).values(id=2))
            assert factory.await_count == 0
        await asyncio.gather(*invalidation.tasks)
        assert factory.await_count == 1
    engine.dispose()


@pytest.mark.asyncio
async def test_multiple_savepoint_levels_do_not_leak_rolled_back_invalidations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = AsyncMock()
    monkeypatch.setattr(invalidation.public_knowledge_cache, 'invalidate', factory)
    engine = create_engine('sqlite://')
    table = Table('qbank_v2_bank_item', MetaData(), Column('id', Integer, primary_key=True))
    table.create(engine)
    with Session(engine) as session:
        with session.begin():
            parent = session.begin_nested()
            with session.begin_nested():
                session.execute(insert(table).values(id=1))
            parent.rollback()
        await asyncio.sleep(0)
        assert factory.await_count == 0
        session.execute(insert(table).values(id=2))
        session.close()
        assert invalidation.PENDING not in session.info
        session.commit()
        await asyncio.sleep(0)
        assert factory.await_count == 0
    engine.dispose()


@pytest.mark.asyncio
async def test_orm_flush_is_tracked_and_user_progress_writes_do_not_invalidate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = AsyncMock()
    monkeypatch.setattr(invalidation.public_knowledge_cache, 'invalidate', factory)
    mapper = registry()
    table = Table('qbank_v2_question_knowledge_point', mapper.metadata, Column('id', Integer, primary_key=True))

    class Link:
        pass

    mapper.map_imperatively(Link, table)
    user_table = Table('qbank_v2_user_bank_item_progress', mapper.metadata, Column('id', Integer, primary_key=True))
    engine = create_engine('sqlite://')
    mapper.metadata.create_all(engine)
    with Session(engine) as session:
        session.add(Link())
        session.commit()
        await asyncio.gather(*invalidation.tasks)
        assert factory.await_count == 1
        session.execute(insert(user_table).values(id=1))
        session.commit()
        await asyncio.sleep(0)
        assert factory.await_count == 1
    mapper.dispose()
    engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize('table_name', sorted(invalidation.TABLES))
async def test_each_public_metadata_write_is_invalidated_after_commit(
    monkeypatch: pytest.MonkeyPatch,
    table_name: str,
) -> None:
    factory = AsyncMock()
    monkeypatch.setattr(invalidation.public_knowledge_cache, 'invalidate', factory)
    engine = create_engine('sqlite://')
    table = Table(table_name, MetaData(), Column('id', Integer, primary_key=True))
    table.create(engine)
    with Session(engine) as session:
        session.execute(insert(table).values(id=1))
        assert factory.await_count == 0
        session.commit()
        await asyncio.gather(*invalidation.tasks)
        assert factory.await_count == 1
        session.execute(update(table).values(id=2).where(table.c.id == 1))
        session.commit()
        await asyncio.gather(*invalidation.tasks)
        assert factory.await_count == 2
        session.execute(table.delete().where(table.c.id == 2))
        session.commit()
        await asyncio.gather(*invalidation.tasks)
        assert factory.await_count == 3
    engine.dispose()
