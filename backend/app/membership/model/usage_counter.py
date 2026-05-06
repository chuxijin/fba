#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, UniversalText, id_key


class MembershipUsageCounter(Base):
    """会员权益用量计数表"""

    __tablename__ = 'membership_usage_counter'
    __table_args__ = (
        sa.UniqueConstraint(
            'user_id',
            'entitlement_code',
            'scope_key',
            'cycle_type',
            'cycle_key',
            name='uq_membership_usage_counter_scope',
        ),
        sa.Index(
            'idx_membership_usage_counter_user_cycle',
            'user_id',
            'entitlement_code',
            'cycle_type',
            'cycle_key',
        ),
        sa.Index('idx_membership_usage_counter_entitlement_cycle', 'entitlement_code', 'cycle_key'),
        {'comment': '会员权益用量计数表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='用户 ID')
    entitlement_code: Mapped[str] = mapped_column(sa.String(64), index=True, comment='权益编码')
    scope_key: Mapped[str] = mapped_column(sa.String(64), default='default', comment='业务范围键')
    cycle_type: Mapped[str] = mapped_column(sa.String(16), default='monthly', comment='周期类型')
    cycle_key: Mapped[str] = mapped_column(sa.String(32), default='lifetime', comment='周期键')
    used_value: Mapped[int] = mapped_column(default=0, comment='已使用数量')
    reserved_value: Mapped[int] = mapped_column(default=0, comment='预留数量')
    limit_value: Mapped[int | None] = mapped_column(default=None, comment='周期额度上限')
    last_used_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最后使用时间')
    last_source: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='最后来源')
    last_source_key: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='最后来源业务键')
    remark: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='备注')
