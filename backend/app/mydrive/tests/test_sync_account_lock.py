#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio

from backend.app.mydrive.service.sync import account_lock


class FakeRedis:
    """内存 Redis 锁替身。"""

    def __init__(self) -> None:
        """初始化内存 Redis 锁替身。"""
        self.values: dict[str, str] = {}
        self.calls: list[tuple[str, tuple]] = []

    async def eval(self, script: str, key_count: int, *args):
        """
        执行锁 Lua 脚本替身。

        :param script: Lua 脚本
        :param key_count: 锁键数量
        :param args: 锁键和脚本参数
        :return:
        """
        self.calls.append((script, args))
        keys = args[:key_count]
        token = args[key_count]
        if script == account_lock._ACQUIRE_LOCKS_SCRIPT:
            if any(key in self.values for key in keys):
                return 0
            for key in keys:
                self.values[key] = token
            return 1
        if script == account_lock._RENEW_LOCKS_SCRIPT:
            return int(all(self.values.get(key) == token for key in keys))
        if script == account_lock._RELEASE_LOCKS_SCRIPT:
            for key in keys:
                if self.values.get(key) == token:
                    del self.values[key]
            return 1
        raise AssertionError('未知 Lua 脚本')


def test_account_lock_acquires_and_releases_all_accounts(monkeypatch) -> None:
    """账户锁应原子覆盖所有参与账户并按令牌释放。"""
    fake_redis = FakeRedis()
    monkeypatch.setattr(account_lock, 'redis_client', fake_redis)

    async def run() -> None:
        lock = account_lock.MyDriveSyncAccountLock({'baidu:10', 'baidu:2'})
        await lock.acquire()
        assert set(fake_redis.values) == {
            'mydrive:sync:account-lock:baidu:10',
            'mydrive:sync:account-lock:baidu:2',
        }
        await lock.release()

    asyncio.run(run())
    assert fake_redis.values == {}


def test_account_lock_rejects_partial_conflict(monkeypatch) -> None:
    """任一账户被占用时不得获取部分锁。"""
    fake_redis = FakeRedis()
    fake_redis.values['mydrive:sync:account-lock:baidu:2'] = 'another-task'
    monkeypatch.setattr(account_lock, 'redis_client', fake_redis)
    monkeypatch.setattr(account_lock, 'MYDRIVE_SYNC_ACCOUNT_LOCK_WAIT_SECONDS', 0)

    async def run() -> None:
        lock = account_lock.MyDriveSyncAccountLock({'baidu:2', 'baidu:10'})
        try:
            await lock.acquire()
        except account_lock.MyDriveSyncAccountLockError:
            return
        raise AssertionError('应拒绝部分账户锁冲突')

    asyncio.run(run())
    assert fake_redis.values == {'mydrive:sync:account-lock:baidu:2': 'another-task'}
