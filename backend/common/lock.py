#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
import uuid

from typing import Optional

from redis.asyncio import Redis
from backend.common.log import log # Import log


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
        log.debug(f"AccountMutex: 尝试获取锁 key={self._key}, token={self._token[:8]}...")
        start_time = asyncio.get_event_loop().time()
        elapsed = 0.0
        while True:
            try:
                ok = await self._redis.set(self._key, self._token, nx=True, ex=self._ttl)
                if ok:
                    log.debug(f"AccountMutex: 成功获取锁 key={self._key}, token={self._token[:8]}...")
                    self._watchdog_task = asyncio.create_task(self._watchdog())
                    return self
            except Exception as e:
                log.error(f"AccountMutex: 获取锁时 Redis 操作失败 key={self._key}, 错误: {e}")

            elapsed = asyncio.get_event_loop().time() - start_time
            if self._max_wait is not None and elapsed >= self._max_wait:
                log.error(f"AccountMutex: 获取锁超时 key={self._key}, 已等待 {elapsed:.2f} 秒")
                raise TimeoutError(f"Acquire lock timeout: {self._key}")
            
            log.debug(f"AccountMutex: 获取锁失败，重试 key={self._key}, 已等待 {elapsed:.2f} 秒")
            await asyncio.sleep(self._retry_interval)

    async def __aexit__(self, exc_type, exc, tb) -> None:
        log.debug(f"AccountMutex: 准备退出锁 key={self._key}, token={self._token[:8]}...")
        if self._watchdog_task and not self._watchdog_task.done():
            self._watchdog_task.cancel()
            try:
                await self._watchdog_task
            except asyncio.CancelledError:
                log.debug(f"AccountMutex: 看门狗任务已取消 key={self._key}")
            except Exception as e:
                log.error(f"AccountMutex: 看门狗任务异常 key={self._key}, 错误: {e}")

        # 仅当 token 匹配时释放锁
        lua = (
            "if redis.call('get', KEYS[1]) == ARGV[1] then "
            "return redis.call('del', KEYS[1]) else return 0 end"
        )
        try:
            del_result = await self._redis.eval(lua, 1, self._key, self._token)
            if del_result == 1:
                log.debug(f"AccountMutex: 成功释放锁 key={self._key}, token={self._token[:8]}...")
            else:
                log.warning(f"AccountMutex: 释放锁失败，token 不匹配或锁已过期 key={self._key}, token={self._token[:8]}...")
        except Exception as e:
            log.error(f"AccountMutex: 释放锁时 Redis 操作失败 key={self._key}, 错误: {e}")
            # 忽略释放异常，过期会自动释放
            pass

    async def _watchdog(self) -> None:
        log.debug(f"AccountMutex: 看门狗任务启动 key={self._key}, token={self._token[:8]}...")
        try:
            while True:
                await asyncio.sleep(self._watchdog_interval)
                # 仅当 token 匹配时续租
                lua = (
                    "if redis.call('get', KEYS[1]) == ARGV[1] then "
                    f"return redis.call('pexpire', KEYS[1], {self._ttl * 1000}) else return 0 end"
                )
                try:
                    續租結果 = await self._redis.eval(lua, 1, self._key, self._token)
                    if 續租結果 == 1:
                        log.debug(f"AccountMutex: 成功续租 key={self._key}, token={self._token[:8]}...")
                    else:
                        log.warning(f"AccountMutex: 续租失败，锁可能已被其他客户端获取或已过期 key={self._key}, token={self._token[:8]}...")
                except Exception as e:
                    log.error(f"AccountMutex: 续租时 Redis 操作失败 key={self._key}, 错误: {e}")
                    # 续租失败时继续下一轮，可能是锁已被释放
                    pass
        except asyncio.CancelledError:
            log.debug(f"AccountMutex: 看门狗任务被取消 key={self._key}")
            return


