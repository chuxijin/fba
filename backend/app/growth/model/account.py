#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class GrowthAccount(Base):
    """用户成长账户表"""

    __tablename__ = 'growth_account'
    __table_args__ = (
        sa.UniqueConstraint('user_id', name='uq_growth_account_user'),
        sa.Index('idx_growth_account_user', 'user_id'),
        {'comment': '用户成长账户'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, comment='用户 ID')
    total_exp: Mapped[int] = mapped_column(default=0, comment='累计经验值')
    available_exp: Mapped[int] = mapped_column(default=0, comment='可用经验值')
    current_grade: Mapped[int] = mapped_column(sa.SmallInteger, default=0, comment='当前等级')
