#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.access.constants import CommonStatus
from backend.common.model import Base, id_key


class StudyDomain(Base):
    """学习领域字典表"""

    __tablename__ = 'study_domain'

    id: Mapped[id_key] = mapped_column(init=False)
    code: Mapped[str] = mapped_column(sa.String(32), unique=True, comment='领域编码')
    name: Mapped[str] = mapped_column(sa.String(64), comment='显示名')
    short_name: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='营销短名')
    parent_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='父级领域 ID')
    icon: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='图标')
    color: Mapped[str | None] = mapped_column(sa.String(16), default=None, comment='主题色')
    description: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='描述')
    display_order: Mapped[int] = mapped_column(default=0, comment='显示顺序')
    metadata_: Mapped[dict] = mapped_column(
        'metadata',
        JSONB,
        default_factory=dict,
        comment='扩展元数据',
    )
    status: Mapped[CommonStatus] = mapped_column(
        PG_ENUM(CommonStatus, name='common_status', create_type=False, values_callable=lambda x: [e.value for e in x]),
        default=CommonStatus.ACTIVE,
        comment='状态',
    )
