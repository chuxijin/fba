#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, UserMixin, id_key

CompatibleJSONB = sa.JSON().with_variant(JSONB, 'postgresql')


class PayOrder(Base, UserMixin):
    """支付业务订单表"""

    __tablename__ = 'pay_order'
    __table_args__ = (
        sa.Index('idx_pay_order_no_unique', 'order_no', unique=True),
        sa.Index('idx_pay_order_user_status', 'user_id', 'status'),
        sa.Index('idx_pay_order_biz_type', 'biz_type'),
        sa.Index('idx_pay_order_created_time', 'created_time'),
        sa.CheckConstraint(
            "status IN ('pending','paid','refund_pending','refunded','closed')",
            name='ck_pay_order_status',
        ),
        sa.CheckConstraint(
            "fulfill_status IN ('pending','fulfilled','failed','revoked')",
            name='ck_pay_order_fulfill_status',
        ),
        sa.CheckConstraint('amount >= 0', name='ck_pay_order_amount'),
        {'comment': '支付业务订单表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    order_no: Mapped[str] = mapped_column(sa.String(64), unique=True, comment='业务订单号')
    user_id: Mapped[int] = mapped_column(sa.BigInteger, comment='支付用户 ID')
    biz_type: Mapped[str] = mapped_column(sa.String(32), comment='业务类型')
    item_code: Mapped[str] = mapped_column(sa.String(128), comment='购买项编码')
    item_name: Mapped[str] = mapped_column(sa.String(256), comment='购买项名称快照')
    amount: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2), comment='支付金额（元）')
    pay_type: Mapped[str] = mapped_column(sa.String(16), default='virtual', comment='支付方式')
    status: Mapped[str] = mapped_column(sa.String(16), default='pending', comment='支付状态')
    fulfill_status: Mapped[str] = mapped_column(sa.String(16), default='pending', comment='发放状态')
    trade_no: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='第三方交易号')
    transaction_no: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='最近内部交易号')
    paid_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='支付成功时间')
    fulfilled_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='权益发放时间')
    refunded_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='退款成功时间')
    closed_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='关闭时间')
    extra_data: Mapped[dict | None] = mapped_column(CompatibleJSONB, default=None, comment='扩展数据')
