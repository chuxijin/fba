import asyncio
import random

from collections.abc import Awaitable, Callable
from time import time
from uuid import uuid4

from opentelemetry import trace

from backend.app.question_bank_v2.schema.knowledge import KnowledgePublicSnapshot
from backend.common.exception import errors
from backend.common.log import log
from backend.database.redis import redis_client

SnapshotFactory = Callable[[], Awaitable[KnowledgePublicSnapshot]]
tracer = trace.get_tracer(__name__)
PREFIX = 'qbank-v2:knowledge:public:v1'
GENERATION_KEY = f'{PREFIX}:generation'
PUBLISH = """
if redis.call('get', KEYS[1]) ~= ARGV[1] then return 0 end
if (redis.call('get', KEYS[2]) or '0') ~= ARGV[2] then return 0 end
redis.call('set', KEYS[3], ARGV[3], 'EX', ARGV[4])
return 1
"""
RELEASE = "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end"


class PublicKnowledgeCache:
    """公共题量缓存：软过期读旧值，跨进程互斥刷新，版本切换阻止旧结果回填。"""

    fresh_seconds = 300
    retention_seconds = 1800
    refresh_seconds = 10
    lock_seconds = 15
    wait_seconds = 17

    def __init__(self) -> None:
        self.tasks: dict[str, asyncio.Task[KnowledgePublicSnapshot | None]] = {}

    async def close(self) -> None:
        """关闭连接池前取消刷新，释放独立会话和刷新锁。"""
        pending = list(self.tasks.values())
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)

    async def invalidate(self) -> None:
        """提交后切换公共缓存版本，旧键自动过期，无需全库扫描。"""
        try:
            await redis_client.set(GENERATION_KEY, uuid4().hex)
        except Exception as exc:
            log.warning(f'[KnowledgeCache] 失效失败，将由软过期刷新兜底: {exc}')

    async def _read(self, key: str) -> KnowledgePublicSnapshot | None:
        raw = await redis_client.get(key)
        if raw is None:
            return None
        try:
            return KnowledgePublicSnapshot.model_validate_json(raw)
        except ValueError:
            # 损坏或旧格式数据当作 miss；不删除可能已被其他进程替换的新值。
            return None

    async def get(
        self, system_id: int, root_id: int | None, revision_id: int | None, *, factory: SnapshotFactory
    ) -> KnowledgePublicSnapshot:
        with tracer.start_as_current_span('qbank.knowledge.public_cache') as span:
            try:
                generation = await redis_client.get(GENERATION_KEY) or '0'
                key = f'{PREFIX}:{generation}:{system_id}:{root_id or 0}:{revision_id or 0}'
                cached = await self._read(key)
            except Exception as exc:
                log.warning(f'[KnowledgeCache] Redis 不可用，合并进程内回源: {exc}')
                span.set_attribute('cache.state', 'unavailable')
                key = f'{PREFIX}:fallback:{system_id}:{root_id or 0}:{revision_id or 0}'
                value = await asyncio.shield(self._start(key, None, factory, stale=False))
                if value is None:
                    raise errors.ServerError(msg='知识点数据刷新中，请稍后重试')
                return value
            if cached is not None and cached.fresh_until > time():
                span.set_attribute('cache.state', 'fresh')
                return cached
            if cached is not None:
                span.set_attribute('cache.state', 'stale')
                self._start(key, generation, factory, stale=True)
                return cached
            span.set_attribute('cache.state', 'miss')
            value = await asyncio.shield(self._start(key, generation, factory, stale=False))
            if value is None:
                raise errors.ServerError(msg='知识点数据刷新中，请稍后重试')
            return value

    def _start(
        self, key: str, generation: str | None, factory: SnapshotFactory, *, stale: bool
    ) -> asyncio.Task[KnowledgePublicSnapshot | None]:
        existing = self.tasks.get(key)
        if existing is not None:
            return existing
        task = asyncio.create_task(self._refresh(key, generation, factory, stale=stale))
        self.tasks[key] = task

        def done(completed: asyncio.Task[KnowledgePublicSnapshot | None]) -> None:
            self.tasks.pop(key, None)
            if not completed.cancelled() and completed.exception() is not None:
                log.warning(f'[KnowledgeCache] 刷新失败 key={key}: {completed.exception()}')

        task.add_done_callback(done)
        return task

    async def _refresh(
        self, key: str, generation: str | None, factory: SnapshotFactory, *, stale: bool
    ) -> KnowledgePublicSnapshot | None:
        if generation is None:
            async with asyncio.timeout(self.refresh_seconds):
                return await factory()
        token = uuid4().hex
        lock_key = f'{key}:lock'
        deadline = asyncio.get_running_loop().time() + self.wait_seconds
        while True:
            try:
                acquired = await redis_client.set(lock_key, token, nx=True, ex=self.lock_seconds)
            except Exception as exc:
                log.warning(f'[KnowledgeCache] 刷新锁不可用，降级回源: {exc}')
                async with asyncio.timeout(self.refresh_seconds):
                    return await factory()
            if acquired:
                break
            if stale:
                return None
            if asyncio.get_running_loop().time() >= deadline:
                raise errors.ServerError(msg='知识点数据刷新中，请稍后重试')
            await asyncio.sleep(0.05)
            try:
                cached = await self._read(key)
            except Exception:
                async with asyncio.timeout(self.refresh_seconds):
                    return await factory()
            if cached is not None:
                return cached
        return await self._fill(key, generation, lock_key, token, factory)

    async def _fill(
        self, key: str, generation: str, lock_key: str, token: str, factory: SnapshotFactory
    ) -> KnowledgePublicSnapshot:
        """锁持有者回源；发布时原子校验锁和版本，始终安全解锁。"""
        try:
            # 等待期间其他刷新可能已经完成，拿到锁后再检查一次。
            try:
                cached = await self._read(key)
            except Exception:
                cached = None
            if cached is not None and cached.fresh_until > time():
                return cached
            async with asyncio.timeout(self.refresh_seconds):
                value = await factory()
            value.fresh_until = time() + self.fresh_seconds * random.uniform(0.9, 1.1)
            try:
                await redis_client.eval(
                    PUBLISH,
                    3,
                    lock_key,
                    GENERATION_KEY,
                    key,
                    token,
                    generation,
                    value.model_dump_json(),
                    self.retention_seconds,
                )
            except Exception as exc:
                log.warning(f'[KnowledgeCache] 写入失败，当前请求仍返回计算结果: {exc}')
            return value
        finally:
            try:
                await redis_client.eval(RELEASE, 1, lock_key, token)
            except Exception as exc:
                log.warning(f'[KnowledgeCache] 解锁失败，等待锁自动过期: {exc}')


public_knowledge_cache = PublicKnowledgeCache()
