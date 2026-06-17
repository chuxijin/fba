#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, id_key
from backend.app.gongkao.model.hanyu import GkHanyu


class GkHanyuNotebook(Base):
    """汉语生词本表"""

    __tablename__ = 'gk_hanyu_notebook'
    __table_args__ = (
        sa.Index('ix_gk_hanyu_notebook_user_hanyu', 'user_id', 'hanyu_id', unique=True),
        {'comment': '汉语生词本表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='用户 ID')
    hanyu_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey('gk_hanyu.id', ondelete='CASCADE'), index=True, comment='汉语词汇 ID'
    )

    # 关系属性
    hanyu: Mapped[GkHanyu] = relationship(init=False, backref='notebook_entries')
