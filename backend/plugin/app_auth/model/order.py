#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DECIMAL, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, id_key
from backend.utils.timezone import timezone

if TYPE_CHECKING:
    from backend.plugin.app_auth.model import AppPackage, AppDevice

class AppOrder(Base):
    """订单表"""

    __tablename__ = 'app_order'

    # 主键和必填字段（没有默认值的字段必须放在前面）
    id: Mapped[id_key] = mapped_column(init=False)
    order_no: Mapped[str] = mapped_column(String(50), unique=True, index=True, comment='订单号')
    total_amount: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), comment='订单总金额')
    package_id: Mapped[int] = mapped_column(
        ForeignKey('app_package.id', ondelete='CASCADE'), comment='套餐ID'
    )
    
    # 有默认值的字段（必须放在后面）
    user_id: Mapped[int | None] = mapped_column(Integer, default=None, comment='用户ID')
    username: Mapped[str | None] = mapped_column(String(50), default=None, comment='用户名')
    contact_info: Mapped[str | None] = mapped_column(String(100), default=None, comment='联系方式')
    paid_amount: Mapped[Decimal] = mapped_column(DECIMAL(10, 2), default=0, comment='已支付金额')
    payment_method: Mapped[str | None] = mapped_column(String(50), default=None, comment='支付方式')
    payment_status: Mapped[int] = mapped_column(default=0, comment='支付状态(0待支付 1已支付 2已退款)')
    order_status: Mapped[int] = mapped_column(default=0, comment='订单状态(0待处理 1已完成 2已取消)')
    device_id: Mapped[int | None] = mapped_column(
        ForeignKey('app_device.id', ondelete='SET NULL'), default=None, comment='设备ID'
    )
    remark: Mapped[str | None] = mapped_column(Text, default=None, comment='备注')
    created_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), init=False, default_factory=timezone.now, comment='创建时间'
    )
    paid_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, comment='支付时间'
    )
    completed_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, comment='完成时间'
    )

    # 关系
    package: Mapped[AppPackage] = relationship(init=False, back_populates='orders', lazy='noload')
    device: Mapped[AppDevice | None] = relationship(init=False, lazy='noload')