#!/usr/bin/env python3
from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.app.payment.model.pay_order import CompatibleJSONB
from backend.common.model import Base, TimeZone, UserMixin, id_key


class PayGroupBuyActivity(Base, UserMixin):
    """订阅拼团活动；发布必须显式配置价格、参与限制和奖励。"""

    __tablename__ = 'pay_group_buy_activity'
    __table_args__ = (
        sa.CheckConstraint("status IN ('draft','active','disabled')", name='ck_pay_gb_activity_status'),
        sa.CheckConstraint('starts_at < ends_at', name='ck_pay_gb_activity_period'),
        {'comment': '支付拼团活动'},
    )
    id: Mapped[id_key] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(sa.String(128))
    template_code: Mapped[str] = mapped_column(sa.String(64))
    starts_at: Mapped[datetime] = mapped_column(TimeZone)
    ends_at: Mapped[datetime] = mapped_column(TimeZone)
    rules: Mapped[dict[str, Any]] = mapped_column(CompatibleJSONB)
    status: Mapped[str] = mapped_column(sa.String(16), default='draft')
    revision: Mapped[int] = mapped_column(default=1)
    description: Mapped[str] = mapped_column(sa.Text, default='')


class PayGroupBuyTier(Base):
    """活动价格档位。"""

    __tablename__ = 'pay_group_buy_tier'
    __table_args__ = (
        sa.UniqueConstraint('activity_id', 'people', name='uq_pay_gb_tier_people'),
        sa.CheckConstraint('people IN (3,4,5)', name='ck_pay_gb_tier_people'),
        sa.CheckConstraint('price_cents > 0', name='ck_pay_gb_tier_price'),
        {'comment': '支付拼团档位'},
    )
    id: Mapped[id_key] = mapped_column(init=False)
    activity_id: Mapped[int] = mapped_column(sa.ForeignKey('pay_group_buy_activity.id', ondelete='RESTRICT'))
    people: Mapped[int] = mapped_column()
    price_cents: Mapped[int] = mapped_column()
    rewards: Mapped[dict[str, Any]] = mapped_column(CompatibleJSONB)


class PayGroupBuyTeam(Base, UserMixin):
    """团：终态不重新打开，采用开团规则快照。"""

    __tablename__ = 'pay_group_buy_team'
    __table_args__ = (
        sa.CheckConstraint(
            "status IN ('draft','forming','succeeded','expired','cancelled')", name='ck_pay_gb_team_status'
        ),
        sa.CheckConstraint('people IN (3,4,5)', name='ck_pay_gb_team_people'),
        sa.Index('idx_pay_gb_team_due', 'status', 'deadline'),
        sa.UniqueConstraint('leader_user_id', 'request_key', name='uq_pay_gb_team_request'),
        {'comment': '支付拼团团队'},
    )
    id: Mapped[id_key] = mapped_column(init=False)
    activity_id: Mapped[int] = mapped_column(sa.ForeignKey('pay_group_buy_activity.id', ondelete='RESTRICT'))
    leader_user_id: Mapped[int] = mapped_column(sa.BigInteger)
    share_code: Mapped[str] = mapped_column(sa.String(32), unique=True)
    request_key: Mapped[str] = mapped_column(sa.String(64))
    people: Mapped[int] = mapped_column()
    snapshot: Mapped[dict[str, Any]] = mapped_column(CompatibleJSONB)
    draft_until: Mapped[datetime] = mapped_column(TimeZone)
    status: Mapped[str] = mapped_column(sa.String(16), default='draft')
    deadline: Mapped[datetime | None] = mapped_column(TimeZone, default=None)
    started_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None)
    succeeded_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None)


class PayGroupBuyMember(Base):
    """账号占位；旧尝试订单保留在支付订单及任务中，不能变成有效名额。"""

    __tablename__ = 'pay_group_buy_member'
    __table_args__ = (
        sa.UniqueConstraint('team_id', 'user_id', name='uq_pay_gb_member_user'),
        sa.UniqueConstraint('order_id', name='uq_pay_gb_member_order'),
        sa.CheckConstraint(
            "status IN ('reserved','paid','expired','refund_pending','refunded')", name='ck_pay_gb_member_status'
        ),
        sa.Index('idx_pay_gb_member_activity_user', 'activity_id', 'user_id'),
        {'comment': '支付拼团成员'},
    )
    id: Mapped[id_key] = mapped_column(init=False)
    team_id: Mapped[int] = mapped_column(sa.ForeignKey('pay_group_buy_team.id', ondelete='RESTRICT'))
    activity_id: Mapped[int] = mapped_column(sa.ForeignKey('pay_group_buy_activity.id', ondelete='RESTRICT'))
    user_id: Mapped[int] = mapped_column(sa.BigInteger)
    reserved_until: Mapped[datetime] = mapped_column(TimeZone)
    order_id: Mapped[int | None] = mapped_column(sa.ForeignKey('pay_order.id', ondelete='RESTRICT'), default=None)
    status: Mapped[str] = mapped_column(sa.String(16), default='reserved')
    inviter_user_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None)
    paid_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None)


class PayGroupBuyTask(Base):
    """持久化业务任务，同时是基础履约、奖励及退款的幂等记录。"""

    __tablename__ = 'pay_group_buy_task'
    __table_args__ = (
        sa.CheckConstraint("kind IN ('payment','base','reward','refund','notify_goods')", name='ck_pay_gb_task_kind'),
        sa.CheckConstraint(
            "status IN ('pending','running','done','failed','manual_review')", name='ck_pay_gb_task_status'
        ),
        sa.Index('idx_pay_gb_task_due', 'status', 'available_at'),
        {'comment': '支付拼团事务任务'},
    )
    id: Mapped[id_key] = mapped_column(init=False)
    key: Mapped[str] = mapped_column(sa.String(128), unique=True)
    kind: Mapped[str] = mapped_column(sa.String(24))
    order_id: Mapped[int] = mapped_column(sa.ForeignKey('pay_order.id', ondelete='RESTRICT'), index=True)
    team_id: Mapped[int] = mapped_column(sa.ForeignKey('pay_group_buy_team.id', ondelete='RESTRICT'))
    payload: Mapped[dict[str, Any]] = mapped_column(CompatibleJSONB, default_factory=dict)
    status: Mapped[str] = mapped_column(sa.String(24), default='pending')
    attempts: Mapped[int] = mapped_column(default=0)
    available_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None)
    lease_until: Mapped[datetime | None] = mapped_column(TimeZone, default=None)
    error: Mapped[str | None] = mapped_column(sa.String(512), default=None)
