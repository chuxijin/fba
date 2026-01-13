#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UniversalText, UserMixin, id_key


class GkShiping(Base, UserMixin):
    """公考时评表"""

    __tablename__ = 'gk_shiping'

    id: Mapped[id_key] = mapped_column(init=False)
    title: Mapped[str] = mapped_column(sa.String(256), comment='标题')
    source: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='来源')
    author: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='作者')
    keywords: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='关键词')
    daily_date: Mapped[date | None] = mapped_column(sa.Date, default=None, index=True, comment='每日时间')
    content: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='内容')
    sidebar: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='右边栏内容')
    mind_map: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='思维导图')
    view_count: Mapped[int] = mapped_column(default=0, comment='阅读量')
