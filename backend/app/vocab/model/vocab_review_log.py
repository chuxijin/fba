#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, id_key


class VocabReviewLog(Base):
    """复习日志表"""

    __tablename__ = 'vocab_review_log'
    __table_args__ = (
        sa.Index('idx_vocab_review_log_user_time', 'user_id', 'reviewed_at'),
        sa.Index('idx_vocab_review_log_word', 'user_id', 'word_id'),
        {'comment': '复习日志表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, comment='用户 ID')
    word_id: Mapped[int] = mapped_column(sa.BigInteger, comment='单词 ID')
    rating: Mapped[int] = mapped_column(sa.SmallInteger, comment='评分(1 Again 2 Hard 3 Good 4 Easy)')
    state: Mapped[int] = mapped_column(sa.SmallInteger, comment='复习时卡片状态')
    review_mode: Mapped[str] = mapped_column(sa.String(20), comment='学习模式')
    reviewed_at: Mapped[datetime] = mapped_column(TimeZone, comment='复习时间')
    duration_ms: Mapped[int | None] = mapped_column(default=None, comment='耗时(毫秒)')
