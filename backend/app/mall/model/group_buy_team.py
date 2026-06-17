#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, TimeZone, UserMixin, id_key
from backend.utils.timezone import timezone


class GroupBuyTeam(Base, UserMixin):
    """拼团团队表"""

    __tablename__ = 'mall_group_buy_team'
    __table_args__ = (
        sa.Index('idx_team_activity_status', 'activity_id', 'status'),
        sa.Index('idx_team_leader_status', 'leader_user_id', 'status'),
        sa.Index('idx_team_expire_time', 'expire_time'),
        sa.CheckConstraint(
            "status IN ('pending','success','failed','cancelled')",
            name='ck_team_status',
        ),
        sa.CheckConstraint('required_people >= 2', name='ck_team_required_people'),
        sa.CheckConstraint('current_people >= 0', name='ck_team_current_people'),
        sa.CheckConstraint('current_people <= required_people', name='ck_team_people_logic'),
        sa.CheckConstraint('team_price >= 0', name='ck_team_price'),
        {'comment': '拼团团队表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    activity_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('mall_group_buy_activity.id', ondelete='CASCADE'),
        comment='活动 ID',
    )
    leader_user_id: Mapped[int] = mapped_column(sa.BigInteger, comment='团长用户 ID')
    required_people: Mapped[int] = mapped_column(sa.Integer, comment='需要人数')
    team_price: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2), comment='拼团价格')
    expire_time: Mapped[datetime] = mapped_column(TimeZone, comment='过期时间')
    current_people: Mapped[int] = mapped_column(sa.Integer, default=0, comment='当前人数')
    status: Mapped[str] = mapped_column(
        sa.String(16), default='pending', comment='状态: pending/success/failed/cancelled'
    )
    start_time: Mapped[datetime] = mapped_column(TimeZone, default_factory=timezone.now, comment='开团时间')
    success_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='成团时间')
    is_mock: Mapped[bool] = mapped_column(default=False, comment='是否模拟成团')
    share_code: Mapped[str | None] = mapped_column(
        sa.String(64), default=None, unique=True, index=True, comment='分享码'
    )

    # ============ 关系 ============
    members: Mapped[list[GroupBuyMember]] = relationship(
        init=False,
        back_populates='team',
        lazy='noload',
        cascade='all, delete-orphan',
    )


class GroupBuyMember(Base, UserMixin):
    """拼团成员表"""

    __tablename__ = 'mall_group_buy_member'
    __table_args__ = (
        sa.UniqueConstraint('team_id', 'user_id', name='uq_member_team_user'),
        sa.Index('idx_member_team_join_time', 'team_id', 'join_time'),
        sa.Index('idx_member_user_activity', 'user_id', 'activity_id'),
        sa.CheckConstraint('paid_amount >= 0', name='ck_member_paid_amount'),
        {'comment': '拼团成员表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    team_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('mall_group_buy_team.id', ondelete='CASCADE'),
        comment='团队 ID',
    )
    activity_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('mall_group_buy_activity.id', ondelete='CASCADE'),
        comment='活动 ID',
    )
    user_id: Mapped[int] = mapped_column(sa.BigInteger, comment='用户 ID')
    paid_amount: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2), comment='支付金额')
    order_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('mall_order.id', ondelete='SET NULL'),
        default=None,
        comment='订单 ID',
    )
    is_leader: Mapped[bool] = mapped_column(default=False, comment='是否团长')
    join_time: Mapped[datetime] = mapped_column(TimeZone, default_factory=timezone.now, comment='参团时间')
    inviter_user_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='邀请人用户 ID')

    # ============ 关系 ============
    team: Mapped[GroupBuyTeam] = relationship(init=False, back_populates='members', lazy='noload')
