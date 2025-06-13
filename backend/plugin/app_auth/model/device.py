#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, id_key
from backend.utils.timezone import timezone

if TYPE_CHECKING:
    from backend.plugin.app_auth.model import AppAuthorization


class AppDevice(Base):
    """设备表"""

    __tablename__ = 'app_device'

    # 主键和必填字段（没有默认值的字段必须放在前面）
    id: Mapped[id_key] = mapped_column(init=False)
    device_id: Mapped[str] = mapped_column(String(100), unique=True, index=True, comment='设备唯一标识')
    
    # 有默认值的字段（必须放在后面）
    device_name: Mapped[str | None] = mapped_column(String(100), default=None, comment='设备名称')
    device_type: Mapped[str | None] = mapped_column(String(50), default=None, comment='设备类型')
    os_info: Mapped[str | None] = mapped_column(String(100), default=None, comment='操作系统信息')
    ip_address: Mapped[str | None] = mapped_column(String(45), default=None, comment='IP地址')
    status: Mapped[int] = mapped_column(default=1, index=True, comment='状态(0禁用 1正常)')
    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), init=False, default_factory=timezone.now, comment='首次发现时间'
    )
    last_seen: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), init=False, onupdate=timezone.now, comment='最后活跃时间'
    )

    # 关系
    authorizations: Mapped[list[AppAuthorization]] = relationship(init=False, back_populates='device', lazy='noload')