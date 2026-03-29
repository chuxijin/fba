#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UniversalText, id_key


class MembershipPlan(Base):
    """会员计划表"""

    __tablename__ = 'membership_plan'
    __table_args__ = (
        sa.UniqueConstraint('name', name='uq_membership_plan_name'),
        sa.Index('idx_membership_plan_tier_status', 'tier_id', 'status'),
        {'comment': '会员计划表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(sa.String(64), comment='计划名称')
    tier_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='会员等级 ID')
    role_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='关联角色 ID')
    duration_days: Mapped[int] = mapped_column(comment='默认时长天数')
    price: Mapped[int] = mapped_column(default=0, comment='价格(分)')
    original_price: Mapped[int] = mapped_column(default=0, comment='原价(分)')
    description: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='权益描述')
    sort: Mapped[int] = mapped_column(default=0, comment='排序')
    status: Mapped[int] = mapped_column(default=1, comment='状态(0下架 1上架)')
