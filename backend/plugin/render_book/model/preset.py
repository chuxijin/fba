#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UniversalText, id_key
from backend.plugin.render_book.model.job import CompatibleJSON


class RenderBookTemplatePreset(Base):
    """题本模板预设表"""

    __tablename__ = 'render_book_template_preset'
    __table_args__ = (
        sa.Index('idx_render_book_template_preset_template', 'template_key', 'sort_order', 'created_time'),
        sa.Index('idx_render_book_template_preset_active', 'template_key', 'is_active'),
        sa.UniqueConstraint('template_key', 'preset_name', name='uq_render_book_template_preset_name'),
        {'comment': '题本模板预设表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    template_key: Mapped[str] = mapped_column(sa.String(100), comment='模板键')
    preset_name: Mapped[str] = mapped_column(sa.String(120), comment='预设名称')
    description: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='预设说明')
    is_active: Mapped[bool] = mapped_column(sa.Boolean, default=True, comment='是否启用')
    is_default: Mapped[bool] = mapped_column(sa.Boolean, default=False, comment='是否默认预设')
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='排序值')
    payload_json: Mapped[dict | None] = mapped_column('payload', CompatibleJSON, default=None, comment='预设配置')
    remark: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='扩展备注')
