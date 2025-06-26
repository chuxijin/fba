#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, id_key
from backend.utils.timezone import timezone

if TYPE_CHECKING:
    from backend.plugin.app_auth.model import AppApplication, AppDevice


class AppAuthorization(Base):
    """授权表"""

    __tablename__ = 'app_authorization'

    # 主键和必填字段（没有默认值的字段必须放在前面）
    id: Mapped[id_key] = mapped_column(init=False)
    auth_type: Mapped[int] = mapped_column(comment='授权类型(1手动 2购买 3兑换码)')
    start_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), comment='授权开始时间'
    )
    application_id: Mapped[int] = mapped_column(
        ForeignKey('app_application.id', ondelete='CASCADE'), comment='应用ID'
    )
    device_id: Mapped[int] = mapped_column(
        ForeignKey('app_device.id', ondelete='CASCADE'), comment='设备ID'
    )
    
    # 有默认值的字段（必须放在后面）
    status: Mapped[int] = mapped_column(default=1, comment='授权状态(0已过期 1正常 2已禁用)')
    end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, comment='授权结束时间'
    )
    remaining_days: Mapped[int | None] = mapped_column(Integer, default=None, comment='剩余天数')
    auth_source: Mapped[str | None] = mapped_column(String(100), default=None, comment='授权来源')
    remark: Mapped[str | None] = mapped_column(Text, default=None, comment='备注')
    created_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), init=False, default_factory=timezone.now, comment='创建时间'
    )
    updated_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), init=False, onupdate=timezone.now, comment='更新时间'
    )

    # 关系
    application: Mapped[AppApplication] = relationship(init=False, back_populates='authorizations', lazy='noload')
    device: Mapped[AppDevice] = relationship(init=False, back_populates='authorizations', lazy='noload')