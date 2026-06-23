#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UserMixin, id_key


class GkHanyu(Base, UserMixin):
    """汉语词汇表"""

    __tablename__ = 'gk_hanyu'
    __table_args__ = (
        sa.Index('ix_gk_hanyu_type_name', 'type', 'name'),
        {'comment': '汉语词汇表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(sa.String(64), index=True, comment='词语名称')
    type: Mapped[str | None] = mapped_column(sa.String(32), default=None, index=True, comment='类型')
    pinyin: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='拼音')
    baobian: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='褒贬色彩')
    structure: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='结构')
    voice: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='语音 URL')
    definition_info: Mapped[dict | None] = mapped_column(JSONB, default=None, comment='定义信息')
    detail_means: Mapped[dict | None] = mapped_column(JSONB, default=None, comment='详细含义')
    liju: Mapped[list | None] = mapped_column(JSONB, default=None, comment='例句')
    antonym: Mapped[list | None] = mapped_column(JSONB, default=None, comment='反义词')
    synonyms: Mapped[list | None] = mapped_column(JSONB, default=None, comment='近义词')
    chu_chu: Mapped[dict | None] = mapped_column(JSONB, default=None, comment='出处')
    yin_zheng: Mapped[dict | None] = mapped_column(JSONB, default=None, comment='引证')
    frequency: Mapped[list | None] = mapped_column(JSONB, default=None, comment='相关题目ID列表')
