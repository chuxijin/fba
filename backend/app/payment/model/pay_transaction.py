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


class PayTransaction(Base, UserMixin):
    """支付记录表"""

    __tablename__ = 'pay_transaction'
    __table_args__ = (
        sa.Index('idx_pay_txn_no', 'transaction_no', unique=True),
        sa.Index('idx_pay_order_no', 'order_no'),
        sa.Index('idx_pay_user_status', 'user_id', 'status'),
        sa.Index('idx_pay_biz_type', 'biz_type'),
        sa.Index('idx_pay_created_time', 'created_time'),
        sa.CheckConstraint(
            "status IN ('pending','paid','refund_pending','refunded','closed')",
            name='ck_pay_txn_status',
        ),
        sa.CheckConstraint('amount >= 0', name='ck_pay_txn_amount'),
        sa.CheckConstraint('refund_amount >= 0', name='ck_pay_txn_refund_amount'),
        {'comment': '支付记录表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    transaction_no: Mapped[str] = mapped_column(sa.String(64), unique=True, comment='内部交易号')
    order_no: Mapped[str] = mapped_column(sa.String(64), comment='业务订单号')
    user_id: Mapped[int] = mapped_column(sa.BigInteger, comment='支付用户 ID')
    pay_type: Mapped[str] = mapped_column(sa.String(16), comment='支付方式: jsapi/h5/virtual')
    amount: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2), comment='支付金额（元）')
    biz_type: Mapped[str] = mapped_column(sa.String(32), comment='业务类型')
    status: Mapped[str] = mapped_column(
        sa.String(16), default='pending', comment='状态: pending/paid/refund_pending/refunded/closed'
    )
    trade_no: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='第三方交易号')
    refund_no: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='商户退款单号')
    refund_amount: Mapped[Decimal | None] = mapped_column(sa.Numeric(10, 2), default=None, comment='已退款金额（元）')
    notify_data: Mapped[dict | None] = mapped_column(CompatibleJSONB, default=None, comment='回调原始数据')
    product_name: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='商品描述快照')
    paid_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='支付成功时间')
    refunded_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='退款成功时间')
    closed_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='关闭时间')
