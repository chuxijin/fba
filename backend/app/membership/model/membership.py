#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, UniversalText, id_key


class UserMembership(Base):
    """用户会员状态表"""

    __tablename__ = 'membership_user'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'family_code', name='uq_membership_user_family'),
        sa.Index('idx_membership_user_active', 'user_id', 'status', 'valid_to'),
        {'comment': '用户会员状态表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='用户 ID')
    family_code: Mapped[str] = mapped_column(sa.String(16), index=True, comment='等级族群')
    tier_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='会员等级 ID')
    tier_code: Mapped[str] = mapped_column(sa.String(32), comment='等级编码快照')
    tier_name: Mapped[str] = mapped_column(sa.String(64), comment='等级名称快照')
    tier_weight: Mapped[int] = mapped_column(sa.SmallInteger, comment='等级权重快照')
    tier_grade: Mapped[int] = mapped_column(sa.SmallInteger, default=0, comment='等级快照')
    exp: Mapped[int] = mapped_column(default=0, comment='经验值')
    valid_from: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='有效期开始')
    valid_to: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='有效期结束')
    source: Mapped[str] = mapped_column(sa.String(32), default='admin', comment='来源')
    source_key: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='来源幂等键')
    status: Mapped[int] = mapped_column(default=1, comment='状态(0取消 1生效 2过期)')
    remark: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='备注')
