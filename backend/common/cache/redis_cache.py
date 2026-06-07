#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio

from collections.abc import Awaitable, Callable
from typing import Any, Generic, TypeVar

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
    ) -> None:
        """
        初始化业务缓存实例

        :param prefix: 缓存键前缀, 例如 'qbank:favorite:statistics'
        :param ttl: Redis 缓存 TTL (秒), 必填以强制业务方明确缓存时效
        :param serializer: 序列化器实例, 决定缓存命中后的对象形态
        :param local: 是否启用 L1 本地缓存, 默认关闭, 仅适合全用户共享数据
        :param invalidate_pubsub: 是否广播失效消息, 仅在 local=True 时生效
        :param single_flight: 是否启用进程内单飞防雪崩, 默认开启
        """
        self._prefix = prefix
        self._ttl = ttl
        self._serializer = serializer
        self._local = local
        self._invalidate_pubsub = invalidate_pubsub and local
        self._single_flight = single_flight
        self._in_flight: dict[str, asyncio.Future[T | None]] = {}

    def _build_key(self, key_parts: tuple[Any, ...]) -> str:
        """根据 key 元组拼接最终 Redis 键"""
        if not key_parts:
            return self._prefix
        suffix = ':'.join(str(part) for part in key_parts)
        return f'{self._prefix}:{suffix}'

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
            return None

        if self._local and value is not None:
            local_cache_manager.set(cache_key, value)
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

        try:
            await redis_client.set(cache_key, payload, ex=self._ttl)
        except Exception as exc:
            log.warning(f'[RedisCache] SET 失败 key={cache_key} err={exc}')
            return

        if self._local:
            local_cache_manager.set(cache_key, value)

    async def get_or_set(
        self,
        *key_parts: Any,
        factory: Callable[[], Awaitable[T | None]],
    ) -> T | None:
        """
        Cache-Aside 一站式 API, 内置 single-flight 防雪崩

        :param key_parts: 组合键, 顺序敏感
        :param factory: miss 时回源函数
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
                if value is not None:
                    await self.set(*key_parts, value=value)
                future.set_result(value)
                return value
            except Exception as exc:
                future.set_exception(exc)
                raise
            finally:
                self._in_flight.pop(cache_key, None)

        value = await factory()
        if value is not None:
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
                await cache_pubsub_manager.publish_invalidation(cache_key, is_delete_prefix=False)
            except Exception as exc:
                log.warning(f'[RedisCache] PUBSUB 失败 key={cache_key} err={exc}')

    async def invalidate_prefix(self, *prefix_parts: Any) -> None:
        """
        按前缀批量失效, 仅失效 key_parts 之后的所有键

        :param prefix_parts: 前缀组合键, 为空时清空整个 prefix 命名空间
        """
        cache_key = self._build_key(prefix_parts)

        if self._local:
            local_cache_manager.delete_prefix(cache_key)

        try:
            await redis_client.delete_prefix(cache_key)
        except Exception as exc:
            log.warning(f'[RedisCache] INVALIDATE_PREFIX 失败 key={cache_key} err={exc}')

        if self._invalidate_pubsub:
            try:
                await cache_pubsub_manager.publish_invalidation(cache_key, is_delete_prefix=True)
            except Exception as exc:
                log.warning(f'[RedisCache] PUBSUB 失败 key={cache_key} err={exc}')
