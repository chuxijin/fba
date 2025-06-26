#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DECIMAL, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import INTEGER
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, id_key
from backend.utils.timezone import timezone

if TYPE_CHECKING:
    from backend.plugin.app_auth.model import AppApplication, AppOrder


class AppPackage(Base):
    """套餐表"""

    __tablename__ = 'app_package'

    # 主键和必填字段（没有默认值的字段必须放在前面）
    id: Mapped[id_key] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(String(100), comment='套餐名称')
    duration_days: Mapped[int] = mapped_column(Integer, comment='有效期天数')
    original_price: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), comment='原价')
    application_id: Mapped[int] = mapped_column(
        ForeignKey('app_application.id', ondelete='CASCADE'), comment='应用ID'
    )
    
    # 有默认值的字段（必须放在后面）
    description: Mapped[str | None] = mapped_column(Text, default=None, comment='套餐描述')
    discount_rate: Mapped[Decimal | None] = mapped_column(DECIMAL(3, 2), default=None, comment='折扣率(0.1-1.0)')
    discount_start_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, comment='折扣开始时间'
    )
    discount_end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, comment='折扣结束时间'
    )
    max_devices: Mapped[int] = mapped_column(Integer, default=1, comment='最大设备数量')
    is_active: Mapped[bool] = mapped_column(
        Boolean().with_variant(INTEGER, 'postgresql'), default=True, comment='是否启用(0否 1是)'
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment='排序')
    created_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), init=False, default_factory=timezone.now, comment='创建时间'
    )
    updated_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), init=False, onupdate=timezone.now, comment='更新时间'
    )

    # 关系
    application: Mapped[AppApplication] = relationship(init=False, back_populates='packages', lazy='noload')
    orders: Mapped[list[AppOrder]] = relationship(init=False, back_populates='package', lazy='noload')