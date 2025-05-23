"""
文件名: drive_accounts.py
描述: 网盘账户表的SQLAlchemy模型
作者: AI助手
创建日期: 2024-05-20
最后修改: 2024-05-20
版本: 1.0.0
"""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, id_key

class DriveAccount(Base):
    """网盘账户模型"""
    
    __tablename__ = "coulddrive_user"
    
    # 基本字段
    id: Mapped[id_key] = mapped_column(init=False)
    type: Mapped[str] = mapped_column(String, nullable=False, index=True)
    accountId: Mapped[str] = mapped_column(String, nullable=False, index=True)
    nickname: Mapped[str | None] = mapped_column(String, nullable=True)
    cookies: Mapped[str | None] = mapped_column(String, nullable=True)
    avatarUrl: Mapped[str | None] = mapped_column(String, nullable=True)
    
    # 配额信息
    quota: Mapped[int] = mapped_column(Integer, default=0)
    used: Mapped[int] = mapped_column(Integer, default=0)
    
    # VIP状态
    isVip: Mapped[int] = mapped_column(Integer, default=0)
    isSupervip: Mapped[int] = mapped_column(Integer, default=0)
    isSupervip_expired: Mapped[int] = mapped_column(Integer, default=0)
    
    # 账号有效性
    isValid: Mapped[int] = mapped_column(Integer, default=1)
    
    # 时间戳
    createTime: Mapped[datetime] = mapped_column(DateTime, default=func.current_timestamp())
    updateTime: Mapped[datetime | None] = mapped_column(DateTime, default=func.current_timestamp(), onupdate=func.current_timestamp())
    
    # 关系
    sync_configs: Mapped[list['SyncConfig']] = relationship(init=False, back_populates="drive_account", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<DriveAccount(id={self.id}, type={self.type}, accountId={self.accountId})>" 