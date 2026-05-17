#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.growth.constants import GrowthEventOp
from backend.common.model import DataClassBase, TimeZone, id_key
from backend.utils.timezone import timezone


class GrowthEvent(DataClassBase):
    """经验值变更流水表(append-only)"""

    __tablename__ = 'growth_event'
    __table_args__ = (
        sa.Index('idx_growth_event_user', 'user_id', 'occurred_at'),
        sa.Index('idx_growth_event_source', 'source', 'source_key'),
        {'comment': '经验值变更流水'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, comment='用户 ID')
    family_code: Mapped[str] = mapped_column(sa.String(16), comment='等级族群')
    operation: Mapped[GrowthEventOp] = mapped_column(
        PG_ENUM(
            GrowthEventOp,
            name='growth_event_op',
            create_type=False,
            values_callable=lambda _: [m.value for m in GrowthEventOp],
        ),
        comment='操作类型',
    )
    exp_delta: Mapped[int] = mapped_column(comment='变动数量(始终为正)')
    total_exp_after: Mapped[int] = mapped_column(comment='操作后累计经验')
    available_exp_after: Mapped[int] = mapped_column(comment='操作后可用经验')
    grade_after: Mapped[int] = mapped_column(sa.SmallInteger, comment='操作后等级')
    source: Mapped[str] = mapped_column(sa.String(32), comment='来源标识')
    source_key: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='来源键')
    idempotency_key: Mapped[str | None] = mapped_column(
        sa.String(128), unique=True, default=None, comment='幂等键'
    )
    reason: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='原因')
    occurred_at: Mapped[datetime] = mapped_column(
        TimeZone, init=False, default_factory=timezone.now, comment='发生时间'
    )
