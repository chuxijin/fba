#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import INTEGER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, id_key
from backend.utils.timezone import timezone

if TYPE_CHECKING:
    from backend.plugin.app_auth.model import AppApplication


class AppRedeemCode(Base):
    """兑换码表"""

    __tablename__ = 'app_redeem_code'

    # 主键和必填字段（没有默认值的字段必须放在前面）
    id: Mapped[id_key] = mapped_column(init=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, comment='兑换码')
    duration_days: Mapped[int] = mapped_column(Integer, comment='有效期天数')
    application_id: Mapped[int] = mapped_column(
        ForeignKey('app_application.id', ondelete='CASCADE'), comment='应用ID'
    )
    
    # 有默认值的字段（必须放在后面）
    batch_no: Mapped[str | None] = mapped_column(String(50), default=None, comment='批次号')
    max_devices: Mapped[int] = mapped_column(Integer, default=1, comment='最大设备数量')
    is_used: Mapped[bool] = mapped_column(
        Boolean().with_variant(INTEGER, 'postgresql'), default=False, comment='是否已使用(0否 1是)'
    )
    used_by: Mapped[str | None] = mapped_column(String(50), default=None, comment='使用者')
    used_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, comment='使用时间'
    )
    expire_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, comment='过期时间'
    )
    remark: Mapped[str | None] = mapped_column(Text, default=None, comment='备注')
    created_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), init=False, default_factory=timezone.now, comment='创建时间'
    )

    # 关系
    application: Mapped[AppApplication] = relationship(init=False, lazy='noload')