#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, UniversalText, id_key


class UserMembership(Base):
    """用户会员记录表"""

    __tablename__ = 'membership_user'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'plan_id', name='uq_membership_user'),
        {'comment': '用户会员记录表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='用户 ID')
    plan_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='会员计划 ID')
    plan_name: Mapped[str] = mapped_column(sa.String(64), comment='计划名称')
    level: Mapped[int] = mapped_column(default=0, comment='会员等级')
    valid_from: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='有效期开始')
    valid_to: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='有效期结束')
    source: Mapped[str] = mapped_column(sa.String(32), default='admin', comment='来源')
    status: Mapped[int] = mapped_column(default=1, comment='状态(0已取消 1生效中 2已过期)')
    remark: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='备注')
