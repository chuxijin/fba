#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class VocabBookWord(Base):
    """词书单词关联表"""

    __tablename__ = 'vocab_book_word'
    __table_args__ = (
        sa.UniqueConstraint('book_id', 'word_id', name='uq_vocab_book_word'),
        sa.Index('idx_vocab_book_word_word_id', 'word_id'),
        {'comment': '词书单词关联表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    book_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='词书 ID')
    word_id: Mapped[int] = mapped_column(sa.BigInteger, comment='单词 ID')
    sort_order: Mapped[int] = mapped_column(default=0, comment='在词书中的顺序')
