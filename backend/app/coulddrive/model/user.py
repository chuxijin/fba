#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import String, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, UserMixin, id_key

if TYPE_CHECKING:
    from backend.app.coulddrive.model.filesync import SyncConfig
    from backend.app.coulddrive.model.file_cache import FileCache
    from backend.app.coulddrive.model.resource import Resource


class DriveAccount(Base, UserMixin):
    """网盘账户表"""
    
    __tablename__ = "yp_user"
    
    id: Mapped[id_key] = mapped_column(init=False)
    type: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="网盘类型")
    user_id: Mapped[str] = mapped_column(String(200), nullable=False, index=True, comment="用户ID")
    
    # 可选字段
    username: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="用户名")
    cookies: Mapped[str | None] = mapped_column(String(5000), nullable=True, comment="登录凭证")
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="头像URL")
    quota: Mapped[int] = mapped_column(BigInteger, default=0, comment="总空间配额")
    used: Mapped[int] = mapped_column(BigInteger, default=0, comment="已使用空间")
    is_vip: Mapped[bool] = mapped_column(default=False, comment="是否VIP用户")
    is_supervip: Mapped[bool] = mapped_column(default=False, comment="是否超级会员")
    is_valid: Mapped[bool] = mapped_column(default=True, comment="账号是否有效")
    
    # 关系
    sync_configs: Mapped[list["SyncConfig"]] = relationship(
        init=False, 
        back_populates="drive_account", 
        cascade="all, delete-orphan"
    )
    file_caches: Mapped[list["FileCache"]] = relationship(
        init=False,
        back_populates="drive_account",
        cascade="all, delete-orphan"
    )
    resources: Mapped[list["Resource"]] = relationship(
        init=False,
        back_populates="user",
        cascade="all, delete-orphan"
    )
    
    def __repr__(self) -> str:
        return f"<DriveAccount(id={self.id}, type={self.type}, user_id={self.user_id})>" 