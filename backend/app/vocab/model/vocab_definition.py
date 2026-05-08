#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class VocabDefinition(Base):
    """单词释义表"""

    __tablename__ = 'vocab_definition'
    __table_args__ = (
        sa.Index('idx_vocab_definition_word_id', 'word_id'),
        {'comment': '单词释义表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    word_id: Mapped[int] = mapped_column(sa.BigInteger, comment='单词 ID')
    meaning: Mapped[str] = mapped_column(sa.String(500), comment='中文释义')
    part_of_speech: Mapped[str | None] = mapped_column(sa.String(20), default=None, comment='词性')
    meaning_en: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='英文释义')
    sort_order: Mapped[int] = mapped_column(default=0, comment='排序')
