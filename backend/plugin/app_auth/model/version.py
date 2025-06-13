#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import INTEGER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, id_key
from backend.utils.timezone import timezone

if TYPE_CHECKING:
    from backend.plugin.app_auth.model import AppApplication


class AppVersion(Base):
    """版本表"""

    __tablename__ = 'app_version'

    # 主键和必填字段（没有默认值的字段必须放在前面）
    id: Mapped[id_key] = mapped_column(init=False)
    version_name: Mapped[str] = mapped_column(String(50), comment='版本名称')
    version_code: Mapped[str] = mapped_column(String(20), comment='版本号')
    application_id: Mapped[int] = mapped_column(
        ForeignKey('app_application.id', ondelete='CASCADE'), comment='应用ID'
    )
    
    # 有默认值的字段（必须放在后面）
    description: Mapped[str | None] = mapped_column(Text, default=None, comment='版本描述')
    download_url: Mapped[str | None] = mapped_column(String(500), default=None, comment='下载地址')
    file_size: Mapped[str | None] = mapped_column(String(20), default=None, comment='文件大小')
    file_hash: Mapped[str | None] = mapped_column(String(64), default=None, comment='文件哈希')
    is_force_update: Mapped[bool] = mapped_column(
        Boolean().with_variant(INTEGER, 'postgresql'), default=False, comment='是否强制更新(0否 1是)'
    )
    is_latest: Mapped[bool] = mapped_column(
        Boolean().with_variant(INTEGER, 'postgresql'), default=False, comment='是否最新版本(0否 1是)'
    )
    status: Mapped[int] = mapped_column(default=1, comment='状态(0下架 1上架)')
    created_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), init=False, default_factory=timezone.now, comment='创建时间'
    )
    updated_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), init=False, onupdate=timezone.now, comment='更新时间'
    )

    # 关系
    application: Mapped[AppApplication] = relationship(init=False, back_populates='versions', lazy='noload')