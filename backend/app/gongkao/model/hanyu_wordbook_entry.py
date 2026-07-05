#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class GkHanyuWordbookEntry(Base):
    """词语本条目表"""

    __tablename__ = 'gk_hanyu_wordbook_entry'
    __table_args__ = (
        sa.UniqueConstraint('wordbook_id', 'hanyu_id', name='uq_hanyu_wordbook_entry'),
        sa.Index('ix_hanyu_wordbook_entry_hanyu', 'hanyu_id'),
        {'comment': '词语本条目表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    wordbook_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='词语本 ID')
    hanyu_id: Mapped[int] = mapped_column(sa.BigInteger, comment='汉语词汇 ID')
    group_name: Mapped[str | None] = mapped_column(sa.String(200), default=None, comment='组名（如第一组 中华文明传统文化）')
    category: Mapped[str | None] = mapped_column(sa.String(100), default=None, comment='子分类（如中华文明传统文化）')
    meaning: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='老师自定义释义')
    commentary: Mapped[str | None] = mapped_column(sa.String(1000), default=None, comment='老师讲解/备注')
    example: Mapped[str | None] = mapped_column(sa.String(1000), default=None, comment='老师例句')
    sort_order: Mapped[int] = mapped_column(default=0, comment='在词语本中的顺序')