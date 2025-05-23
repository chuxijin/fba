"""
文件名: sync_task_item.py
描述: 同步任务项表的SQLAlchemy模型
作者: AI助手
创建日期: 2024-05-20
最后修改: 2024-05-20
版本: 1.0.0
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func, Text, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, id_key

class CouldDriveFileSyncTaskItem(Base):
    """同步任务项模型"""
    
    __tablename__ = "coulddrivefilesync_task_item"
    
    # 基本字段
    id: Mapped[id_key] = mapped_column(init=False)
    taskId = Mapped[int] = mapped_column(Integer, ForeignKey("coulddrivefilesync_task.id", ondelete="CASCADE"), nullable=False, index=True)
    type = Mapped[str] = mapped_column(String, nullable=False)  # 操作类型（delete/rename/copy）
    
    # 文件信息
    srcPath = Mapped[str] = mapped_column(String, nullable=False)  # 源文件路径
    dstPath = Mapped[str] = mapped_column(String, nullable=False)  # 目标文件路径
    fileName = Mapped[str] = mapped_column(String, nullable=False)  # 文件名
    fileSize = Mapped[int] = mapped_column(BigInteger, default=0)   # 文件大小（单位：字节）
    
    # 任务状态
    status = Mapped[str] = mapped_column(String, default="pending", index=True)  # 状态（pending/running/completed/failed）
    errMsg = Mapped[str | None] = mapped_column(Text, nullable=True)  # 错误信息
    
    # 时间戳
    createTime = Mapped[datetime] = mapped_column(DateTime, default=func.current_timestamp())
    
    # 关系
    sync_task = relationship("CouldDriveFileSyncTask", back_populates="task_items")
    
    def __repr__(self):
        return f"<CouldDriveFileSyncTaskItem(id={self.id}, fileName={self.fileName}, status={self.status})>" 