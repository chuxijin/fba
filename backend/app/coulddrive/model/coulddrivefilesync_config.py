"""
文件名: sync_config.py
描述: 同步配置表的SQLAlchemy模型
作者: AI助手
创建日期: 2024-05-20
最后修改: 2024-05-20
版本: 1.0.0
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, id_key

class CouldDriveFileSyncConfig(Base):
    """同步配置模型"""
    
    __tablename__ = "coulddrivefilesync_config"
    
    # 基本字段
    id: Mapped[id_key] = mapped_column(init=False)
    enable = Mapped[int] = mapped_column(Integer, default=1)
    remark = Mapped[str | None] = mapped_column(String, nullable=True)
    type = Mapped[str] = mapped_column(String, nullable=False, index=True)
    
    # 路径信息
    srcPath = Mapped[str] = mapped_column(String, nullable=False)
    srcMeta = Mapped[str | None] = mapped_column(Text, nullable=True)
    dstPath = Mapped[str] = mapped_column(String, nullable=False)
    dstMeta = Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # 关联账号
    accountId = Mapped[int] = mapped_column(Integer, ForeignKey("coulddrive_user.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # 同步配置
    corn = Mapped[str | None] = mapped_column(String, nullable=True)    # 定时任务表达式
    speed = Mapped[int] = mapped_column(Integer, default=0)      # 同步速度
    method = Mapped[str] = mapped_column(String, default="copy") # 同步方法（copy/move）
    
    # 其他配置
    endTime = Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    exclude = Mapped[str | None] = mapped_column(Text, nullable=True)    # 排除规则（JSON格式）
    rename = Mapped[str | None] = mapped_column(Text, nullable=True)     # 重命名规则（JSON格式）
    
    # 时间戳
    lastSync = Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    createTime = Mapped[datetime] = mapped_column(DateTime, default=func.current_timestamp())
    updateTime = Mapped[datetime] = mapped_column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # 关系
    drive_account = relationship("CouldDriveUser", back_populates="sync_configs")
    sync_tasks = relationship("CouldDriveFileSyncTask", back_populates="sync_config", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<CouldDriveFileSyncConfig(id={self.id}, type={self.type})>" 