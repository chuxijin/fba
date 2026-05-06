from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.coulddrive.model.filesync_lock import FileSyncLock
from backend.common.exception.errors import CustomError
from backend.common.log import log
from backend.common.response.response_code import CustomErrorCode
from backend.utils.timezone import timezone


class CRUDFilesyncLock(CRUDPlus[FileSyncLock]):
    """文件同步锁的 CRUD 操作"""

    async def get_by_key(self, db: AsyncSession, lock_key: str) -> FileSyncLock | None:
        """根据 lock_key 获取文件同步锁记录"""
        stmt = select(self.model).where(self.model.lock_key == lock_key)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def create_lock(self, db: AsyncSession, lock_key: str, owner_id: str, expires_at: datetime) -> FileSyncLock:
        """
        创建新的文件同步锁记录。
        利用数据库的唯一约束来确保原子性。
        """
        new_lock = self.model(
            lock_key=lock_key,
            owner_id=owner_id,
            expires_at=expires_at,
        )
        db.add(new_lock)
        try:
            await db.commit()
            await db.refresh(new_lock)
            log.debug(f"成功创建文件同步锁: {lock_key}, 持有者: {owner_id}")
            return new_lock
        except IntegrityError as e:
            await db.rollback()
            log.warning(f"创建文件同步锁失败，lock_key: {lock_key} 已存在或冲突: {e}")
            raise CustomError(
                CustomErrorCode.LOCK_ACQUISITION_FAILED,
                f"尝试获取锁失败，{lock_key} 已被占用或发生冲突。",
            ) from e
        except Exception as e:
            await db.rollback()
            log.error(f"创建文件同步锁时发生未知错误: {e}")
            raise e

    async def update_lock(self, db: AsyncSession, lock_record: FileSyncLock, owner_id: str, expires_at: datetime) -> FileSyncLock:
        """
        更新文件同步锁记录。
        用于续租或更改持有者。
        """
        lock_record.owner_id = owner_id
        lock_record.expires_at = expires_at # 只需要更新过期时间
        try:
            await db.commit()
            await db.refresh(lock_record)
            log.debug(f"成功更新文件同步锁: {lock_record.lock_key}, 新到期时间: {expires_at}")
            return lock_record
        except Exception as e:
            await db.rollback()
            log.error(f"更新文件同步锁 {lock_record.lock_key} 时发生错误: {e}")
            raise e

    async def release_lock(self, db: AsyncSession, lock_record: FileSyncLock) -> None:
        """释放文件同步锁（删除记录）"""
        await db.delete(lock_record)
        try:
            await db.commit()
            log.debug(f"成功释放文件同步锁: {lock_record.lock_key}")
        except Exception as e:
            await db.rollback()
            log.error(f"释放文件同步锁 {lock_record.lock_key} 时发生错误: {e}")
            raise e

    async def acquire_lock_transaction(
        self, db: AsyncSession, lock_key: str, owner_id: str, timeout_seconds: int
    ) -> FileSyncLock | None:
        """
        尝试在事务中原子地获取文件同步锁。
        如果锁不存在，则创建；如果锁已过期，则抢占；否则等待。
        """
        current_time = timezone.now()
        new_expires_at = current_time + timedelta(seconds=timeout_seconds)

        try:
            # 尝试获取现有锁并锁定行
            stmt = select(self.model).where(self.model.lock_key == lock_key).with_for_update()
            existing_lock = await db.execute(stmt)
            lock_record = existing_lock.scalar_one_or_none()

            if lock_record:
                # 锁存在
                if lock_record.expires_at <= current_time:
                    # 锁已过期，尝试抢占
                    log.info(f"文件同步锁 {lock_key} 已过期，尝试抢占。原持有者: {lock_record.owner_id}")
                    lock_record.owner_id = owner_id
                    lock_record.expires_at = new_expires_at
                    # last_renewed_at 会由 Base 模型的 updated_time 自动更新
                    await db.commit()
                    await db.refresh(lock_record)
                    log.info(f"成功抢占文件同步锁: {lock_key}, 新持有者: {owner_id}")
                    return lock_record
                else:
                    # 锁未过期，无法获取
                    log.debug(f"文件同步锁 {lock_key} 未过期，当前持有者: {lock_record.owner_id}，等待中...")
                    await db.rollback() # 释放行锁
                    return None
            else:
                # 锁不存在，创建新锁
                log.debug(f"文件同步锁 {lock_key} 不存在，尝试创建。")
                new_lock = self.model(
                    lock_key=lock_key,
                    owner_id=owner_id,
                    expires_at=new_expires_at,
                )
                db.add(new_lock)
                await db.commit()
                await db.refresh(new_lock)
                log.info(f"成功创建文件同步锁: {lock_key}, 持有者: {owner_id}")
                return new_lock

        except IntegrityError as e:
            await db.rollback()
            log.warning(f"并发冲突: 文件同步锁 {lock_key} 在尝试获取时发生并发插入/更新冲突: {e}")
            return None # 另一个并发事务已经成功获取，或者在等待中
        except Exception as e:
            await db.rollback()
            log.error(f"获取文件同步锁 {lock_key} 时发生未知错误: {e}")
            raise e


crud_filesync_lock = CRUDFilesyncLock(FileSyncLock)
