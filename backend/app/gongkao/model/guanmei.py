#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""官媒学言语模型"""
from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UniversalText, UserMixin, id_key


class GkGuanmei(Base, UserMixin):
    """官媒学言语表（成语积累、逻辑填空等）"""

    __tablename__ = 'gk_guanmei'

    id: Mapped[id_key] = mapped_column(init=False)
    daily_date: Mapped[date | None] = mapped_column(sa.Date, default=None, index=True, comment='日期')
    left_content: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='左栏内容（文段）')
    right_content: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='右栏内容（解析）')
    view_count: Mapped[int] = mapped_column(default=0, comment='阅读量')
