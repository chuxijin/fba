#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import uuid

from typing import Optional

from redis.asyncio import Redis


class AccountMutex:
    """
    账号级异步分布式互斥锁

    使用 Redis 实现的简易互斥：SET NX + TTL，退出时校验 token 再释放。
    适用于需要将同一账号下的写操作（删除/转存/创建/重命名）串行化的场景。
    """

    def __init__(
        self,
        redis: Redis,
        key: str,
        ttl_seconds: int = 300,
        retry_interval_seconds: float = 0.5,
        watchdog_interval_seconds: float = 20.0,
        max_wait_seconds: Optional[int] = None,
    ) -> None:
        """
        :param redis: Redis 客户端
        :param key: 锁 key（建议使用 filesync:{drive_type}:{user_id}）
        :param ttl_seconds: 锁过期时间（秒）
        :param retry_interval_seconds: 抢锁失败后的重试间隔（秒）
        :param watchdog_interval_seconds: 看门狗续租间隔（秒）
        :param max_wait_seconds: 获取锁的最大等待时间，None 表示无限等待
        :return:
        """
        self._redis = redis
        self._key = f"lock:{key}"
        self._ttl = int(ttl_seconds)
        self._retry_interval = float(retry_interval_seconds)
        self._watchdog_interval = float(watchdog_interval_seconds)
        self._max_wait = max_wait_seconds
        self._token: str = uuid.uuid4().hex
        self._watchdog_task: Optional[asyncio.Task] = None

    async def __aenter__(self) -> "AccountMutex":
        elapsed = 0.0
        while True:
            ok = await self._redis.set(self._key, self._token, nx=True, ex=self._ttl)
            if ok:
                self._watchdog_task = asyncio.create_task(self._watchdog())
                return self
            if self._max_wait is not None and elapsed >= self._max_wait:
                raise TimeoutError(f"Acquire lock timeout: {self._key}")
            await asyncio.sleep(self._retry_interval)
            elapsed += self._retry_interval

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._watchdog_task and not self._watchdog_task.done():
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except Exception:
                pass

        # 仅当 token 匹配时释放锁
        lua = (
            "if redis.call('get', KEYS[1]) == ARGV[1] then "
            "return redis.call('del', KEYS[1]) else return 0 end"
        )
        try:
            await self._redis.eval(lua, 1, self._key, self._token)
        except Exception:
            # 忽略释放异常，过期会自动释放
            pass

    async def _watchdog(self) -> None:
        try:
            while True:
                await asyncio.sleep(self._watchdog_interval)
                # 仅当 token 匹配时续租
                lua = (
                    "if redis.call('get', KEYS[1]) == ARGV[1] then "
                    f"return redis.call('pexpire', KEYS[1], {self._ttl * 1000}) else return 0 end"
                )
                try:
                    await self._redis.eval(lua, 1, self._key, self._token)
                except Exception:
                    # 续租失败时继续下一轮，可能是锁已被释放
                    pass
        except asyncio.CancelledError:
            return


