#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class VocabExample(Base):
    """例句表"""

    __tablename__ = 'vocab_example'
    __table_args__ = (
        sa.Index('idx_vocab_example_word_id', 'word_id'),
        {'comment': '例句表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    word_id: Mapped[int] = mapped_column(sa.BigInteger, comment='单词 ID')
    sentence_en: Mapped[str] = mapped_column(sa.String(500), comment='英文例句')
    definition_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='关联释义 ID')
    sentence_zh: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='中文翻译')
    source: Mapped[str | None] = mapped_column(sa.String(100), default=None, comment='来源')
    sort_order: Mapped[int] = mapped_column(default=0, comment='排序')
