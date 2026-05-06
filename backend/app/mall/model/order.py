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


class Order(Base, UserMixin):
    """订单表"""

    __tablename__ = 'mall_order'
    __table_args__ = (
        sa.Index('idx_order_user_status', 'user_id', 'status'),
        sa.Index('idx_order_team_status', 'team_id', 'status'),
        sa.Index('idx_order_no', 'order_no', unique=True),
        sa.Index('idx_order_trade_no', 'trade_no'),
        sa.Index('idx_order_created_time', 'created_time'),
        sa.CheckConstraint(
            "status IN ('pending','paid','cancelled','refunded','completed')",
            name='ck_order_status',
        ),
        sa.CheckConstraint(
            "order_type IN ('normal','group_buy')",
            name='ck_order_type',
        ),
        sa.CheckConstraint('total_amount >= 0', name='ck_order_total_amount'),
        sa.CheckConstraint('paid_amount >= 0', name='ck_order_paid_amount'),
        {'comment': '订单表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    order_no: Mapped[str] = mapped_column(sa.String(64), unique=True, comment='订单号')
    user_id: Mapped[int] = mapped_column(sa.BigInteger, comment='用户 ID')
    product_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('mall_product.id', ondelete='RESTRICT'),
        comment='商品 ID',
    )
    sku_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('mall_product_sku.id', ondelete='RESTRICT'),
        comment='SKU ID',
    )
    product_name: Mapped[str] = mapped_column(sa.String(256), comment='商品名称（快照）')
    sku_name: Mapped[str] = mapped_column(sa.String(128), comment='SKU 名称（快照）')
    unit_price: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2), comment='单价')
    total_amount: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2), comment='订单总额')
    order_type: Mapped[str] = mapped_column(
        sa.String(16), default='normal', comment='订单类型: normal/group_buy'
    )
    quantity: Mapped[int] = mapped_column(sa.Integer, default=1, comment='购买数量')
    paid_amount: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2), default=Decimal('0'), comment='已支付金额')
    status: Mapped[str] = mapped_column(
        sa.String(16), default='pending', comment='状态: pending/paid/cancelled/refunded/completed'
    )
    pay_type: Mapped[str | None] = mapped_column(sa.String(16), default=None, comment='支付方式(jsapi/h5)')
    trade_no: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='第三方交易号')
    team_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('mall_group_buy_team.id', ondelete='SET NULL'),
        default=None,
        comment='拼团团队 ID',
    )
    activity_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('mall_group_buy_activity.id', ondelete='SET NULL'),
        default=None,
        comment='拼团活动 ID',
    )
    remark: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='订单备注')
    extra_data: Mapped[dict | None] = mapped_column(CompatibleJSONB, default=None, comment='扩展数据')
    paid_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='支付时间')
    cancelled_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='取消时间')
    refunded_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='退款时间')
    completed_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='完成时间')
