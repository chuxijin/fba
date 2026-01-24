#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UniversalText, UserMixin, id_key


class GkJingyan(Base, UserMixin):
    """公考经验表"""

    __tablename__ = 'gk_jingyan'

    id: Mapped[id_key] = mapped_column(init=False)

    # 基础信息（必填字段）
    title: Mapped[str] = mapped_column(sa.String(256), comment='标题')
    type: Mapped[str] = mapped_column(sa.String(50), index=True, comment='分类')
    content: Mapped[str] = mapped_column(UniversalText, comment='内容')

    # 基础信息（可选字段）
    author: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='作者')
    tags: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='标签（逗号分隔）')
    daily_date: Mapped[date | None] = mapped_column(sa.Date, default=None, index=True, comment='发布日期')
    summary: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='摘要')

    # 统计信息
    view_count: Mapped[int] = mapped_column(default=0, comment='阅读量')
