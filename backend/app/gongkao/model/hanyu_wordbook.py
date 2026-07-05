#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UserMixin, id_key


class GkHanyuWordbook(Base, UserMixin):
    """汉语词语本表"""

    __tablename__ = 'gk_hanyu_wordbook'
    __table_args__ = (
        sa.Index('ix_gk_hanyu_wordbook_teacher_status', 'teacher_id', 'status'),
        {'comment': '汉语词语本表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(sa.String(100), comment='词语本名称')
    teacher_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='老师用户 ID')
    description: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='词语本描述')
    cover_image: Mapped[str | None] = mapped_column(sa.String(255), default=None, comment='封面图 URL')
    category: Mapped[str] = mapped_column(sa.String(50), default='custom', comment='分类')
    word_count: Mapped[int] = mapped_column(default=0, comment='词语总数')
    is_official: Mapped[bool] = mapped_column(default=False, comment='是否官方预置')
    sort_order: Mapped[int] = mapped_column(default=0, comment='排序')
    status: Mapped[int] = mapped_column(sa.SmallInteger, default=1, comment='状态(0 下架 1 上架)')