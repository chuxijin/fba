"""
文件名: sync_task.py
描述: 同步任务表的SQLAlchemy模型
作者: AI助手
创建日期: 2024-05-20
最后修改: 2024-07-25
版本: 1.1.0
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, id_key


class CouldDriveFileSyncTask(Base):
    """同步任务模型"""
    
    __tablename__ = "coulddrivefilesync_task"
    
    # 基本字段
    id: Mapped[id_key] = mapped_column(init=False)
    configId = Mapped[int] = mapped_column(Integer, ForeignKey("sync_config.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Mapped[str] = mapped_column(String, default="pending", index=True)
    errMsg = Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 任务执行信息
    startTime = Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    taskNum = Mapped[int] = mapped_column(Integer, default=0)  # 总任务数量
    
    # 持续时间
    duraTime = Mapped[int] = mapped_column(Integer, default=0)  # 持续时间（单位：秒）
    
    # 时间戳
    createTime = Mapped[datetime] = mapped_column(DateTime, default=func.current_timestamp())
    
    # 关系
    sync_config = relationship("CouldDriveFileSyncConfig", back_populates="sync_tasks")
    task_items = relationship("CouldDriveFileSyncTaskItem", back_populates="sync_task", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<CouldDriveFileSyncTask(id={self.id}, status={self.status})>" 