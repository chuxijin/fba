#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, TimeZone, UserMixin, id_key

CompatibleJSONB = sa.JSON().with_variant(JSONB, 'postgresql')


class GroupBuyActivity(Base, UserMixin):
    """拼团活动表"""

    __tablename__ = 'mall_group_buy_activity'
    __table_args__ = (
        sa.Index('idx_activity_product_status', 'product_id', 'status'),
        sa.Index('idx_activity_time_status', 'start_time', 'end_time', 'status'),
        sa.CheckConstraint(
            "status IN ('draft','active','paused','ended')",
            name='ck_activity_status',
        ),
        sa.CheckConstraint('min_people >= 2', name='ck_activity_min_people'),
        sa.CheckConstraint('max_people >= min_people', name='ck_activity_max_people'),
        sa.CheckConstraint('time_limit > 0', name='ck_activity_time_limit'),
        sa.CheckConstraint('stock >= 0', name='ck_activity_stock'),
        sa.CheckConstraint('sales_count >= 0', name='ck_activity_sales'),
        {'comment': '拼团活动表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    product_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('mall_product.id', ondelete='CASCADE'),
        comment='商品 ID',
    )
    sku_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('mall_product_sku.id', ondelete='CASCADE'),
        comment='SKU ID',
    )
    activity_name: Mapped[str] = mapped_column(sa.String(256), comment='活动名称')
    min_people: Mapped[int] = mapped_column(sa.Integer, comment='最小成团人数')
    max_people: Mapped[int] = mapped_column(sa.Integer, comment='最大成团人数')
    time_limit: Mapped[int] = mapped_column(sa.Integer, comment='成团时限（小时）')
    start_time: Mapped[datetime] = mapped_column(TimeZone, comment='活动开始时间')
    end_time: Mapped[datetime] = mapped_column(TimeZone, comment='活动结束时间')
    stock: Mapped[int] = mapped_column(sa.Integer, default=0, comment='活动库存')
    sales_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='已售数量')
    status: Mapped[str] = mapped_column(
        sa.String(16), default='draft', comment='状态: draft/active/paused/ended'
    )
    enable_mock_team: Mapped[bool] = mapped_column(default=False, comment='是否启用模拟成团')
    mock_team_threshold: Mapped[int | None] = mapped_column(
        sa.Integer, default=None, comment='模拟成团阈值（剩余多少人时触发）'
    )
    share_config: Mapped[dict | None] = mapped_column(CompatibleJSONB, default=None, comment='分享配置')
    rules: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='活动规则说明')

    # ============ 关系 ============
    ladder_prices: Mapped[list[GroupBuyLadderPrice]] = relationship(
        init=False,
        back_populates='activity',
        lazy='noload',
        cascade='all, delete-orphan',
    )


class GroupBuyLadderPrice(Base, UserMixin):
    """拼团阶梯价格表"""

    __tablename__ = 'mall_group_buy_ladder_price'
    __table_args__ = (
        sa.UniqueConstraint('activity_id', 'people_count', name='uq_ladder_price_activity_people'),
        sa.Index('idx_ladder_price_activity', 'activity_id'),
        sa.CheckConstraint('people_count >= 2', name='ck_ladder_price_people'),
        sa.CheckConstraint('price >= 0', name='ck_ladder_price_price'),
        {'comment': '拼团阶梯价格表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    activity_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('mall_group_buy_activity.id', ondelete='CASCADE'),
        comment='活动 ID',
    )
    people_count: Mapped[int] = mapped_column(sa.Integer, comment='成团人数')
    price: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2), comment='拼团价格')
    original_price: Mapped[Decimal | None] = mapped_column(
        sa.Numeric(10, 2), default=None, comment='原价'
    )

    # ============ 关系 ============
    activity: Mapped[GroupBuyActivity] = relationship(init=False, back_populates='ladder_prices', lazy='noload')
