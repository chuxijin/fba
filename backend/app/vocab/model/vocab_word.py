#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UserMixin, id_key


class VocabWord(Base, UserMixin):
    """单词表"""

    __tablename__ = 'vocab_word'
    __table_args__ = (
        sa.Index('idx_vocab_word_frequency', 'frequency'),
        {'comment': '单词表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    word: Mapped[str] = mapped_column(sa.String(100), unique=True, index=True, comment='单词')
    phonetic_us: Mapped[str | None] = mapped_column(sa.String(100), default=None, comment='美式音标')
    phonetic_uk: Mapped[str | None] = mapped_column(sa.String(100), default=None, comment='英式音标')
    audio_us_url: Mapped[str | None] = mapped_column(sa.String(255), default=None, comment='美式发音 URL')
    audio_uk_url: Mapped[str | None] = mapped_column(sa.String(255), default=None, comment='英式发音 URL')
    common_meaning: Mapped[str | None] = mapped_column(sa.String(200), default=None, comment='常用释义')
    frequency: Mapped[int] = mapped_column(default=0, comment='词频等级')
