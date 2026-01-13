#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UniversalText, UserMixin, id_key


class GkShizhen(Base, UserMixin):
    """公考时政表"""

    __tablename__ = 'gk_shizhen'

    id: Mapped[id_key] = mapped_column(init=False)
    daily_date: Mapped[date | None] = mapped_column(sa.Date, default=None, index=True, comment='日期')
    original: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='原文')
    summary: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='主要内容')
