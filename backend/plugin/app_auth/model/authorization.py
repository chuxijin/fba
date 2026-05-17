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

    id: Mapped[id_key] = mapped_column(init=False)
    source: Mapped[str] = mapped_column(String(32), comment='授权来源(manual/purchase/redeem_code)')
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), comment='授权开始时间'
    )
    application_id: Mapped[int] = mapped_column(
        ForeignKey('app_application.id', ondelete='CASCADE'), comment='应用ID'
    )
    device_id: Mapped[int] = mapped_column(
        ForeignKey('app_device.id', ondelete='CASCADE'), comment='设备ID'
    )

    status: Mapped[str] = mapped_column(
        String(32), default='active', comment='授权状态(active/expired/paused)'
    )
    valid_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, comment='授权结束时间'
    )
    remaining_days: Mapped[int | None] = mapped_column(Integer, default=None, comment='剩余天数')
    source_ref: Mapped[str | None] = mapped_column(String(100), default=None, comment='来源引用(订单号/兑换码等)')
    template_code: Mapped[str | None] = mapped_column(
        String(120), default=None, comment='关联 access.subscription_template.code'
    )
    remark: Mapped[str | None] = mapped_column(Text, default=None, comment='备注')
    created_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), init=False, default_factory=timezone.now, comment='创建时间'
    )
    updated_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), init=False, onupdate=timezone.now, comment='更新时间'
    )

    application: Mapped[AppApplication] = relationship(init=False, back_populates='authorizations', lazy='noload')
    device: Mapped[AppDevice] = relationship(init=False, back_populates='authorizations', lazy='noload')
