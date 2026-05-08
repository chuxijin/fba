#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UserMixin, id_key


class VocabBook(Base, UserMixin):
    """词书表"""

    __tablename__ = 'vocab_book'
    __table_args__ = (
        sa.Index('idx_vocab_book_category_status', 'category', 'status'),
        {'comment': '词书表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(sa.String(100), comment='词书名称')
    description: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='词书描述')
    cover_image: Mapped[str | None] = mapped_column(sa.String(255), default=None, comment='封面图 URL')
    category: Mapped[str] = mapped_column(sa.String(50), default='custom', comment='分类')
    word_count: Mapped[int] = mapped_column(default=0, comment='词汇总数')
    is_official: Mapped[bool] = mapped_column(default=False, comment='是否官方预置')
    creator_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='创建者用户 ID')
    sort_order: Mapped[int] = mapped_column(default=0, comment='排序')
    status: Mapped[int] = mapped_column(sa.SmallInteger, default=1, comment='状态(0 下架 1 上架)')
