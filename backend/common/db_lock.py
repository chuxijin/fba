import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Callable, Self

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.coulddrive.crud.crud_filesync_lock import crud_filesync_lock
from backend.app.coulddrive.model.filesync_lock import FileSyncLock
from backend.common.exception.errors import CustomError
from backend.common.response.response_code import CustomErrorCode
from backend.common.log import log


class DatabaseMutex:
    """基于数据库实现的分布式互斥锁"""

    def __init__(
        self,
        db_session_factory: Callable[[], AsyncSession],
        lock_key: str,
        owner_id: str | None = None,
        timeout_seconds: int = 60, # 锁的默认持有时间，秒
        max_wait_seconds: int = 300, # 最大等待锁的时间，秒
        retry_interval_seconds: float = 0.5, # 尝试获取锁的间隔时间，秒
        renew_interval_seconds: int = 15, # 锁续租间隔时间，秒
    ):
        self.db_session_factory = db_session_factory
        self.lock_key = lock_key
        self.owner_id = owner_id or str(uuid.uuid4()) # 如果未提供，则生成一个唯一的持有者ID
        self.timeout_seconds = timeout_seconds
        self.max_wait_seconds = max_wait_seconds
        self.retry_interval_seconds = retry_interval_seconds
        self.renew_interval_seconds = renew_interval_seconds
        self.lock_record: FileSyncLock | None = None
        self._renew_task: asyncio.Task | None = None

    async def __aenter__(self) -> Self:
        """进入上下文，尝试获取锁"""
        start_time = datetime.now()
        log.info(f"尝试获取数据库锁: {self.lock_key}, 持有者: {self.owner_id}")

        while (datetime.now() - start_time).total_seconds() < self.max_wait_seconds:
            async with self.db_session_factory() as db:
                try:
                    acquired_lock = await crud_filesync_lock.acquire_lock_transaction(
                        db,
                        self.lock_key,
                        self.owner_id,
                        self.timeout_seconds,
                    )
                    if acquired_lock:
                        self.lock_record = acquired_lock
                        self._start_renew_task() # 启动续租任务
                        log.info(f"成功获取数据库锁: {self.lock_key}, 持有者: {self.owner_id}")
                        return self
                    else:
                        # 锁被占用，等待重试
                        log.debug(
                            f"数据库锁 {self.lock_key} 被占用，等待 {self.retry_interval_seconds} 秒后重试..."
                        )
                        await asyncio.sleep(self.retry_interval_seconds)
                except CustomError as e:
                    if e.code == CustomErrorCode.LOCK_ACQUISITION_FAILED.code: # 确保这里使用 CustomErrorCode
                        log.warning(
                            f"数据库锁 {self.lock_key} 获取失败（并发冲突或已过期被占用），等待重试: {e.detail}"
                        )
                        await asyncio.sleep(self.retry_interval_seconds)
                    else:
                        log.error(f"获取数据库锁时发生自定义错误: {e}")
                        raise
                except Exception as e:
                    log.error(f"获取数据库锁 {self.lock_key} 时发生未知错误: {e}")
                    raise
        
        # 超过最大等待时间仍未获取到锁
        log.warning(f"获取数据库锁超时: {self.lock_key}, 最大等待时间: {self.max_wait_seconds} 秒")
        raise TimeoutError(f"Failed to acquire lock {self.lock_key} within {self.max_wait_seconds} seconds")

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """退出上下文，释放锁"""
        if self._renew_task:
            self._renew_task.cancel() # 取消续租任务
            try:
                await self._renew_task
            except asyncio.CancelledError:
                pass
            log.debug(f"已取消数据库锁 {self.lock_key} 的续租任务。")

        if self.lock_record:
            async with self.db_session_factory() as db:
                try:
                    await crud_filesync_lock.release_lock(db, self.lock_record) # 删除锁记录
                    log.info(f"成功释放数据库锁: {self.lock_key}, 持有者: {self.owner_id}")
                except Exception as e:
                    log.error(f"释放数据库锁 {self.lock_key} 时发生错误: {e}")
        else:
            log.warning(f"尝试释放一个未成功获取的数据库锁: {self.lock_key}")

    def _start_renew_task(self) -> None:
        """启动后台续租任务"""
        if self._renew_task and not self._renew_task.done():
            return # 任务已在运行

        self._renew_task = asyncio.create_task(self._renew_loop()) # 创建并调度续租协程
        log.debug(f"已启动数据库锁 {self.lock_key} 的续租任务。")

    async def _renew_loop(self) -> None:
        """续租循环，定期更新锁的到期时间"""
        while True:
            try:
                await asyncio.sleep(self.renew_interval_seconds)
                if self.lock_record:
                    async with self.db_session_factory() as db:
                        # 重新加载锁记录以确保最新状态
                        current_lock_record = await crud_filesync_lock.get_by_key(db, self.lock_key)
                        if current_lock_record and current_lock_record.owner_id == self.owner_id:
                            # 只有当锁仍然存在且由当前实例持有者持有，才进行续租
                            new_expires_at = datetime.now() + timedelta(seconds=self.timeout_seconds)
                            await crud_filesync_lock.update_lock(db, current_lock_record, self.owner_id, new_expires_at)
                            self.lock_record = current_lock_record # 更新内部引用
                            log.debug(f"数据库锁 {self.lock_key} 续租成功，新到期时间: {new_expires_at}")
                        else:
                            log.warning(f"数据库锁 {self.lock_key} 已丢失或被抢占，停止续租。")
                            break # 锁已丢失或被抢占，停止续租
                else:
                    log.warning(f"数据库锁 {self.lock_key} 记录丢失，停止续租。")
                    break
            except asyncio.CancelledError:
                log.debug(f"数据库锁 {self.lock_key} 续租任务被取消。")
                break
            except Exception as e:
                log.error(f"数据库锁 {self.lock_key} 续租时发生错误: {e}")
                # 这里不应该直接break，可以考虑更复杂的错误处理或通知机制
                await asyncio.sleep(5) # 出现错误时稍等再重试，避免快速循环
