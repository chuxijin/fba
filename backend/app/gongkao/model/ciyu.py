#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UniversalText, UserMixin, id_key


class GkCiyu(Base, UserMixin):
    """公考词语表"""

    __tablename__ = 'gk_ciyu'

    id: Mapped[id_key] = mapped_column(init=False)

    # 基础信息（必填字段）
    word: Mapped[str] = mapped_column(sa.String(64), index=True, comment='词语')

    # 基础信息（可选字段）
    meaning: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='释义')
    pinyin: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='拼音')
    synonym: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='近义词')
    antonym: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='反义词')
    example: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='例句')
    category: Mapped[str | None] = mapped_column(sa.String(32), default=None, index=True, comment='分类')
    source: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='出处')
    emotion: Mapped[str | None] = mapped_column(sa.String(16), default=None, comment='感情色彩')
    confusion: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='易混辨析')
    frequency: Mapped[int | None] = mapped_column(sa.SmallInteger, default=None, comment='考频')

    # 统计信息
    view_count: Mapped[int] = mapped_column(default=0, comment='阅读量')
