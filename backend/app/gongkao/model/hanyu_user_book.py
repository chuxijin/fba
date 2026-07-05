#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, id_key


class GkHanyuUserBook(Base):
    """用户学习词语本表"""

    __tablename__ = 'gk_hanyu_user_book'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'book_id', name='uq_hanyu_user_book'),
        sa.Index('ix_hanyu_user_book_active', 'user_id', 'is_active'),
        {'comment': '用户学习词语本表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='用户 ID')
    book_id: Mapped[int] = mapped_column(sa.BigInteger, comment='词语本 ID')
    is_active: Mapped[bool] = mapped_column(default=True, comment='是否当前在学')
    started_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='开始学习时间')
    finished_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='完成时间')