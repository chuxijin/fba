#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, UniversalText, id_key


class MembershipRecord(Base):
    """会员发放流水表"""

    __tablename__ = 'membership_record'
    __table_args__ = (
        sa.UniqueConstraint(
            'user_id',
            'family_code',
            'source',
            'source_key',
            'op_type',
            name='uq_membership_record_idempotent',
        ),
        sa.Index('idx_membership_record_user_created', 'user_id', 'created_time'),
        sa.Index('idx_membership_record_source', 'source', 'source_key'),
        {'comment': '会员发放流水表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='用户 ID')
    family_code: Mapped[str] = mapped_column(sa.String(16), index=True, comment='等级族群')
    tier_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='会员等级 ID')
    days: Mapped[int] = mapped_column(comment='变动天数(正数增加 负数扣减)')
    source: Mapped[str] = mapped_column(sa.String(32), comment='来源标识')
    source_key: Mapped[str] = mapped_column(sa.String(64), comment='来源幂等键')
    plan_id: Mapped[int | None] = mapped_column(sa.BigInteger, index=True, default=None, comment='会员计划 ID')
    op_type: Mapped[str] = mapped_column(sa.String(16), default='grant', comment='操作类型')
    exp_delta: Mapped[int] = mapped_column(default=0, comment='经验变动值')
    source_detail: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='来源详情')
    valid_to_before: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='变动前到期时间')
    valid_to_after: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='变动后到期时间')
    remark: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='备注')
