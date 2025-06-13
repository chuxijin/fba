#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.dialects.postgresql import INTEGER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, id_key
from backend.utils.timezone import timezone

if TYPE_CHECKING:
    from backend.plugin.app_auth.model import AppVersion, AppPackage, AppAuthorization


class AppApplication(Base):
    """应用表"""

    __tablename__ = 'app_application'

    id: Mapped[id_key] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True, comment='应用名称')
    app_key: Mapped[str] = mapped_column(String(50), unique=True, index=True, comment='应用标识')
    description: Mapped[str | None] = mapped_column(Text, default=None, comment='应用描述')
    icon: Mapped[str | None] = mapped_column(String(255), default=None, comment='应用图标')
    status: Mapped[int] = mapped_column(default=1, index=True, comment='状态(0停用 1启用)')
    is_free: Mapped[bool] = mapped_column(
        Boolean().with_variant(INTEGER, 'postgresql'), default=False, comment='是否免费(0否 1是)'
    )
    created_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), init=False, default_factory=timezone.now, comment='创建时间'
    )
    updated_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), init=False, onupdate=timezone.now, comment='更新时间'
    )

    # 关系
    versions: Mapped[list[AppVersion]] = relationship(init=False, back_populates='application', lazy='noload')
    packages: Mapped[list[AppPackage]] = relationship(init=False, back_populates='application', lazy='noload')
    authorizations: Mapped[list[AppAuthorization]] = relationship(init=False, back_populates='application', lazy='noload')