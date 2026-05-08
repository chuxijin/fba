#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, id_key
from backend.utils.timezone import timezone


class VocabGroupWord(Base):
    """学习组单词关联表"""

    __tablename__ = 'vocab_group_word'
    __table_args__ = (
        sa.UniqueConstraint('group_id', 'word_id', name='uq_vocab_group_word'),
        sa.Index('idx_vocab_group_word_word_id', 'word_id'),
        {'comment': '学习组单词关联表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    group_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='学习组 ID')
    word_id: Mapped[int] = mapped_column(sa.BigInteger, comment='单词 ID')
    added_at: Mapped[datetime] = mapped_column(TimeZone, default_factory=timezone.now, comment='加入时间')
