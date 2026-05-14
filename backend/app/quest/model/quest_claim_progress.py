#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, id_key
from backend.utils.timezone import timezone


class QuestClaimProgress(Base):
    """悬赏任务进度幂等流水表"""

    __tablename__ = 'quest_claim_progress'
    __table_args__ = (
        sa.UniqueConstraint('claim_id', 'source_key', name='uq_claim_progress_source'),
        sa.Index('idx_claim_progress_claim', 'claim_id'),
        {'comment': '悬赏任务进度幂等流水表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    claim_id: Mapped[int] = mapped_column(sa.BigInteger, comment='领取记录 ID')
    source_key: Mapped[str] = mapped_column(sa.String(128), comment='事件唯一幂等键(如 invite_relation:123)')
    occurred_at: Mapped[datetime] = mapped_column(
        TimeZone,
        default_factory=timezone.now,
        comment='事件发生时间',
    )
