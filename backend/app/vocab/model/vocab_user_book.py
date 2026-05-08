#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, id_key


class VocabUserBook(Base):
    """用户学习词书表"""

    __tablename__ = 'vocab_user_book'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'book_id', name='uq_vocab_user_book'),
        sa.Index('idx_vocab_user_book_active', 'user_id', 'is_active'),
        {'comment': '用户学习词书表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='用户 ID')
    book_id: Mapped[int] = mapped_column(sa.BigInteger, comment='词书 ID')
    is_active: Mapped[bool] = mapped_column(default=True, comment='是否当前在学')
    started_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='开始学习时间')
    finished_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='完成时间')
