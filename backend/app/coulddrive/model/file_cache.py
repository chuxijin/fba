#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String, BigInteger, Boolean, DateTime, ForeignKey, Text, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, id_key

if TYPE_CHECKING:
    from backend.app.coulddrive.model.user import DriveAccount


class FileCache(Base):
    """文件缓存表"""
    
    __tablename__ = "file_cache"
    
    id: Mapped[id_key] = mapped_column(init=False)
    file_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True, comment="文件唯一ID")
    file_name: Mapped[str] = mapped_column(String(500), nullable=False, comment="文件名称")
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False, index=True, comment="文件路径")
    
    # 关联网盘账户
    drive_account_id: Mapped[int] = mapped_column(
        ForeignKey("yp_user.id", ondelete="CASCADE"), 
        nullable=False, 
        index=True, 
        comment="关联网盘账户ID"
    )
    
    # 可选字段（必须在有默认值的字段之前）
    parent_id: Mapped[str | None] = mapped_column(String(200), nullable=True, index=True, comment="父目录ID", init=False)
    
    # 有默认值的字段
    is_folder: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否为文件夹", init=False)
    
    # 文件属性（可选字段）
    file_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True, comment="文件大小", init=False)
    file_created_at: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="文件创建时间", init=False)
    file_updated_at: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="文件更新时间", init=False)
    
    # 扩展信息（可选字段）
    file_ext: Mapped[str | None] = mapped_column(Text, nullable=True, comment="扩展信息JSON", init=False)
    
    # 缓存相关（可选字段）
    cache_version: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="缓存版本", init=False)
    
    # 有默认值的字段
    is_valid: Mapped[bool] = mapped_column(Boolean, default=True, comment="缓存是否有效", init=False)
    
    # 关系
    drive_account: Mapped["DriveAccount"] = relationship(
        "DriveAccount",
        back_populates="file_caches",
        init=False
    )
    
    # 索引
    __table_args__ = (
        Index('idx_drive_file', 'drive_account_id', 'file_id'),
        Index('idx_drive_path', 'drive_account_id', 'file_path'),
        Index('idx_drive_parent', 'drive_account_id', 'parent_id'),
        {'comment': '文件缓存表'}
    )
    
    def __repr__(self) -> str:
        return f"<FileCache(id={self.id}, file_name={self.file_name}, drive_account_id={self.drive_account_id})>" 