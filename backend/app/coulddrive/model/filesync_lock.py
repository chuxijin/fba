
from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column  # 导入 Mapped 和 mapped_column

from backend.common.model import Base


class FileSyncLock(Base):
    """文件同步锁表"""

    __tablename__ = "filesync_lock"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="主键ID")
    lock_key: Mapped[str] = mapped_column(String(255), nullable=False, comment="锁的唯一键，格式通常为 filesync:{drive_type}:{user_id}")
    owner_id: Mapped[str | None] = mapped_column(String(255), nullable=True, comment="当前持有锁的任务ID或标识符")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, comment="锁的到期时间，在此时间前必须续租")

    __table_args__ = (
        UniqueConstraint("lock_key", name="uq_filesync_lock_key"),
        {"comment": "文件同步分布式锁表"},
    )
