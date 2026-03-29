#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UniversalText, id_key


class MembershipTierEntitlement(Base):
    """等级权益映射表"""

    __tablename__ = 'membership_tier_entitlement'
    __table_args__ = (
        sa.UniqueConstraint('tier_id', 'entitlement_id', name='uq_membership_tier_entitlement'),
        sa.Index('idx_membership_tier_entitlement_tier', 'tier_id', 'status'),
        {'comment': '等级权益映射表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    tier_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='会员等级 ID')
    entitlement_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='权益 ID')
    entitlement_code: Mapped[str] = mapped_column(sa.String(64), index=True, comment='权益编码快照')
    value: Mapped[int] = mapped_column(default=1, comment='权益值')
    status: Mapped[int] = mapped_column(default=1, comment='状态(0停用 1启用)')
    description: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='描述')
