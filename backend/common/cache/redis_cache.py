#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import random

from collections.abc import Awaitable, Callable
from typing import Any, Generic, TypeVar
from urllib.parse import quote

from backend.common.cache.local import local_cache_manager
from backend.common.cache.pubsub import cache_pubsub_manager
from backend.common.cache.serializers import Serializer
from backend.common.log import log
from backend.database.redis import redis_client

T = TypeVar('T')


class RedisCache(Generic[T]):
    """业务层 Redis 缓存抽象 (Cache-Aside + 短 TTL + per-cache 配置)"""

    def __init__(
        self,
        prefix: str,
        ttl: int,
        serializer: Serializer[T],
        *,
        local: bool = False,
        invalidate_pubsub: bool = False,
        single_flight: bool = True,
        ttl_jitter: float = 0.1,
    ) -> None:
        """
        初始化业务缓存实例

        :param prefix: 缓存键前缀, 例如 'qbank:favorite:statistics'
        :param ttl: Redis 缓存 TTL (秒), 必填以强制业务方明确缓存时效
        :param serializer: 序列化器实例, 决定缓存命中后的对象形态
        :param local: 是否启用 L1 本地缓存, 默认关闭, 仅适合全用户共享数据
        :param invalidate_pubsub: 是否广播失效消息, 仅在 local=True 时生效
        :param single_flight: 是否启用进程内单飞防雪崩, 默认开启
        :param ttl_jitter: TTL 随机抖动比例，避免大量缓存同时过期
        """
        normalized_prefix = prefix.strip().strip(':')
        if not normalized_prefix:
            raise ValueError('cache prefix must not be empty')
        if ttl <= 0:
            raise ValueError('cache ttl must be greater than zero')
        if invalidate_pubsub and not local:
            raise ValueError('invalidate_pubsub requires local=True')
        if not 0 <= ttl_jitter <= 0.5:
            raise ValueError('cache ttl_jitter must be between 0 and 0.5')

        self._prefix = normalized_prefix
        self._ttl = ttl
        self._serializer = serializer
        self._local = local
        self._invalidate_pubsub = invalidate_pubsub and local
        self._single_flight = single_flight
        self._ttl_jitter = ttl_jitter
        self._in_flight: dict[str, asyncio.Future[T | None]] = {}

    @staticmethod
    def _normalize_key_part(part: Any) -> str:
        if part is None:
            value = 'none'
        elif isinstance(part, bool):
            value = 'true' if part else 'false'
        else:
            value = str(part)
        return quote(value, safe='-_.~')

    def _build_key(self, key_parts: tuple[Any, ...]) -> str:
        """根据 key 元组拼接最终 Redis 键"""
        if not key_parts:
            return self._prefix
        suffix = ':'.join(self._normalize_key_part(part) for part in key_parts)
        return f'{self._prefix}:{suffix}'

    def _effective_ttl(self) -> int:
        if self._ttl_jitter == 0:
            return self._ttl
        factor = 1 + random.uniform(-self._ttl_jitter, self._ttl_jitter)
        return max(1, round(self._ttl * factor))

    async def _set_local_from_redis(self, cache_key: str, value: T) -> None:
        """使用 Redis 剩余 TTL 回填 L1，避免延长缓存生命周期。"""
        try:
            remaining_ttl = await redis_client.ttl(cache_key)
        except Exception as exc:
            log.warning(f'[RedisCache] TTL 读取失败 key={cache_key} err={exc}')
            return
        if remaining_ttl > 0:
            local_cache_manager.set(cache_key, value, ttl=remaining_ttl)

    async def get(self, *key_parts: Any) -> T | None:
        """
        读取缓存, miss 时返回 None, 异常静默降级

        :param key_parts: 组合键, 顺序敏感
        """
        cache_key = self._build_key(key_parts)

        if self._local:
            local_value = local_cache_manager.get(cache_key)
            if local_value is not None:
                return local_value

        try:
            raw = await redis_client.get(cache_key)
        except Exception as exc:
            log.warning(f'[RedisCache] GET 失败 key={cache_key} err={exc}')
            return None

        if raw is None:
            return None

        try:
            value = self._serializer.decode(raw)
        except Exception as exc:
            log.warning(f'[RedisCache] DECODE 失败 key={cache_key} err={exc}')
            try:
                await redis_client.delete(cache_key)
            except Exception:
                pass
            return None

        if self._local and value is not None:
            await self._set_local_from_redis(cache_key, value)
        return value

    async def set(self, *key_parts: Any, value: T) -> None:
        """
        写入缓存, 异常静默降级

        :param key_parts: 组合键, 顺序敏感
        :param value: 待缓存的值
        """
        if value is None:
            return
        cache_key = self._build_key(key_parts)

        try:
            payload = self._serializer.encode(value)
        except Exception as exc:
            log.warning(f'[RedisCache] ENCODE 失败 key={cache_key} err={exc}')
            return

        effective_ttl = self._effective_ttl()
        try:
            await redis_client.set(cache_key, payload, ex=effective_ttl)
        except Exception as exc:
            log.warning(f'[RedisCache] SET 失败 key={cache_key} err={exc}')
            return

        if self._local:
            local_cache_manager.set(cache_key, value, ttl=effective_ttl)

    async def get_or_set(
        self,
        *key_parts: Any,
        factory: Callable[[], Awaitable[T | None]],
        should_cache: Callable[[T], bool] | None = None,
    ) -> T | None:
        """
        Cache-Aside 一站式 API, 内置 single-flight 防雪崩

        :param key_parts: 组合键, 顺序敏感
        :param factory: miss 时回源函数
        :param should_cache: 可选缓存条件，返回 False 时只返回回源结果而不写缓存
        """
        cached = await self.get(*key_parts)
        if cached is not None:
            return cached

        cache_key = self._build_key(key_parts)

        if self._single_flight:
            existing = self._in_flight.get(cache_key)
            if existing is not None:
                return await existing

            loop = asyncio.get_running_loop()
            future: asyncio.Future[T | None] = loop.create_future()
            self._in_flight[cache_key] = future
            try:
                value = await factory()
                if value is not None and (should_cache is None or should_cache(value)):
                    await self.set(*key_parts, value=value)
            except BaseException as exc:
                future.set_exception(exc)
                # Consume the exception so a single caller does not produce an
                # unhandled-future warning while still notifying waiters.
                future.exception()
                raise
            else:
                future.set_result(value)
                return value
            finally:
                self._in_flight.pop(cache_key, None)

        value = await factory()
        if value is not None and (should_cache is None or should_cache(value)):
            await self.set(*key_parts, value=value)
        return value

    async def invalidate(self, *key_parts: Any) -> None:
        """
        失效单个键, 同步处理 L1 / L2 / Pub-Sub

        :param key_parts: 组合键, 顺序敏感
        """
        cache_key = self._build_key(key_parts)

        if self._local:
            local_cache_manager.delete(cache_key)

        try:
            await redis_client.delete(cache_key)
        except Exception as exc:
            log.warning(f'[RedisCache] INVALIDATE 失败 key={cache_key} err={exc}')

        if self._invalidate_pubsub:
            try:
                await cache_pubsub_manager.publish_invalidation(cache_key, delete_by_prefix=False)
            except Exception as exc:
                log.warning(f'[RedisCache] PUBSUB 失败 key={cache_key} err={exc}')

    async def invalidate_prefix(self, *prefix_parts: Any) -> None:
        """
        按前缀批量失效, 仅失效 key_parts 之后的所有键

        :param prefix_parts: 前缀组合键, 为空时清空整个 prefix 命名空间
        """
        cache_key = self._build_key(prefix_parts)

        if self._local:
            local_cache_manager.delete_by_prefix(cache_key)

        try:
            await redis_client.delete_prefix(cache_key)
        except Exception as exc:
            log.warning(f'[RedisCache] INVALIDATE_PREFIX 失败 key={cache_key} err={exc}')

        if self._invalidate_pubsub:
            try:
                await cache_pubsub_manager.publish_invalidation(cache_key, delete_by_prefix=True)
            except Exception as exc:
                log.warning(f'[RedisCache] PUBSUB 失败 key={cache_key} err={exc}')
