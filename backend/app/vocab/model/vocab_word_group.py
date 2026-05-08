#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class VocabWordGroup(Base):
    """学习组表"""

    __tablename__ = 'vocab_word_group'
    __table_args__ = (
        sa.Index('idx_vocab_word_group_user', 'user_id'),
        {'comment': '学习组表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, comment='用户 ID')
    name: Mapped[str] = mapped_column(sa.String(50), comment='组名')
    description: Mapped[str | None] = mapped_column(sa.String(200), default=None, comment='描述')
    color: Mapped[str | None] = mapped_column(sa.String(20), default=None, comment='标签颜色')
    sort_order: Mapped[int] = mapped_column(default=0, comment='排序')
