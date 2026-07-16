#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
import time
import uuid

from backend.database.redis import redis_client


MYDRIVE_SYNC_ACCOUNT_LOCK_TTL_SECONDS = 120
MYDRIVE_SYNC_ACCOUNT_LOCK_RENEW_INTERVAL_SECONDS = 30
MYDRIVE_SYNC_ACCOUNT_LOCK_WAIT_SECONDS = 600
MYDRIVE_SYNC_ACCOUNT_LOCK_RETRY_INTERVAL_SECONDS = 1

_ACQUIRE_LOCKS_SCRIPT = """
for index = 1, #KEYS do
    if redis.call('exists', KEYS[index]) == 1 then
        return 0
    end
end
for index = 1, #KEYS do
    redis.call('set', KEYS[index], ARGV[1], 'PX', ARGV[2])
end
return 1
"""
_RENEW_LOCKS_SCRIPT = """
for index = 1, #KEYS do
    if redis.call('get', KEYS[index]) ~= ARGV[1] then
        return 0
    end
end
for index = 1, #KEYS do
    redis.call('pexpire', KEYS[index], ARGV[2])
end
return 1
"""
_RELEASE_LOCKS_SCRIPT = """
for index = 1, #KEYS do
    if redis.call('get', KEYS[index]) == ARGV[1] then
        redis.call('del', KEYS[index])
    end
end
return 1
"""


class MyDriveSyncAccountLockError(Exception):
    """MyDrive 同步账户锁异常。"""


class MyDriveSyncAccountLock:
    """MyDrive 同步账户分布式锁。"""

    def __init__(self, account_keys: set[str]) -> None:
        """
        初始化账户分布式锁。

        :param account_keys: 网盘账户锁标识集合
        :return:
        """
        self._keys = [f'mydrive:sync:account-lock:{key}' for key in sorted(account_keys)]
        self._token = uuid.uuid4().hex
        self._renew_task: asyncio.Task[None] | None = None
        self._lease_lost = False

    @property
    def lease_lost(self) -> bool:
        """判断账户锁租约是否已丢失。"""
        return self._lease_lost

    async def acquire(self) -> None:
        """等待并原子获取全部账户锁。"""
        if not self._keys:
            return
        deadline = time.monotonic() + MYDRIVE_SYNC_ACCOUNT_LOCK_WAIT_SECONDS
        while time.monotonic() < deadline:
            try:
                acquired = await redis_client.eval(
                    _ACQUIRE_LOCKS_SCRIPT,
                    len(self._keys),
                    *self._keys,
                    self._token,
                    MYDRIVE_SYNC_ACCOUNT_LOCK_TTL_SECONDS * 1000,
                )
            except Exception as exc:
                raise MyDriveSyncAccountLockError(f'获取网盘账户同步锁失败: {exc}') from exc
            if acquired:
                self._renew_task = asyncio.create_task(self._renew_loop())
                return
            await asyncio.sleep(MYDRIVE_SYNC_ACCOUNT_LOCK_RETRY_INTERVAL_SECONDS)
        raise MyDriveSyncAccountLockError('等待网盘账户同步锁超时')

    async def release(self) -> None:
        """释放当前任务持有的账户锁。"""
        if self._renew_task is not None:
            self._renew_task.cancel()
            try:
                await self._renew_task
            except asyncio.CancelledError:
                pass
        if not self._keys:
            return
        try:
            await redis_client.eval(_RELEASE_LOCKS_SCRIPT, len(self._keys), *self._keys, self._token)
        except Exception:
            return

    async def _renew_loop(self) -> None:
        """定期续期当前账户锁租约。"""
        while True:
            await asyncio.sleep(MYDRIVE_SYNC_ACCOUNT_LOCK_RENEW_INTERVAL_SECONDS)
            try:
                renewed = await redis_client.eval(
                    _RENEW_LOCKS_SCRIPT,
                    len(self._keys),
                    *self._keys,
                    self._token,
                    MYDRIVE_SYNC_ACCOUNT_LOCK_TTL_SECONDS * 1000,
                )
            except Exception:
                self._lease_lost = True
                return
            if not renewed:
                self._lease_lost = True
                return


@asynccontextmanager
async def acquire_sync_account_lock(account_keys: set[str]) -> AsyncIterator[MyDriveSyncAccountLock]:
    """获取 MyDrive 同步账户锁。"""
    lock = MyDriveSyncAccountLock(account_keys)
    await lock.acquire()
    try:
        yield lock
    finally:
        await lock.release()
