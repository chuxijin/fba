#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UniversalText, id_key


class MembershipTier(Base):
    """会员等级表"""

    __tablename__ = 'membership_tier'
    __table_args__ = (
        sa.UniqueConstraint('code', name='uq_membership_tier_code'),
        sa.UniqueConstraint('weight', name='uq_membership_tier_weight'),
        sa.UniqueConstraint('family_code', 'grade', name='uq_membership_tier_family_grade'),
        sa.Index('idx_membership_tier_status_sort', 'status', 'sort'),
        {'comment': '会员等级表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    family_code: Mapped[str] = mapped_column(sa.String(16), comment='等级族群(FREE/VIP/SVIP)')
    code: Mapped[str] = mapped_column(sa.String(32), comment='等级编码')
    name: Mapped[str] = mapped_column(sa.String(64), comment='等级名称')
    weight: Mapped[int] = mapped_column(sa.SmallInteger, comment='等级权重')
    grade: Mapped[int] = mapped_column(sa.SmallInteger, default=0, comment='族群内等级')
    exp_required: Mapped[int] = mapped_column(default=0, comment='达到该等级所需经验')
    sort: Mapped[int] = mapped_column(default=0, comment='排序')
    is_default: Mapped[bool] = mapped_column(default=False, comment='是否默认等级')
    status: Mapped[int] = mapped_column(default=1, comment='状态(0停用 1启用)')
    description: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='描述')
