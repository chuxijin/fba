#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM, JSONB, TSTZRANGE
from sqlalchemy.dialects.postgresql.ranges import Range
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.access.constants import CommonStatus, TemplateKind
from backend.common.model import Base, id_key


def _enum_values(enum_cls: type) -> list[str]:
    """ENUM values_callable 工具"""
    return [member.value for member in enum_cls]


class SubscriptionTemplate(Base):
    """订阅模板表"""

    __tablename__ = 'subscription_template'

    id: Mapped[id_key] = mapped_column(init=False)
    code: Mapped[str] = mapped_column(sa.String(64), unique=True, comment='模板编码')
    name: Mapped[str] = mapped_column(sa.String(128), comment='模板名称')
    kind: Mapped[TemplateKind] = mapped_column(
        PG_ENUM(
            TemplateKind,
            name='template_kind',
            create_type=False,
            values_callable=lambda x: _enum_values(TemplateKind),
        ),
        default=TemplateKind.STANDARD,
        comment='模板类型',
    )
    duration_days: Mapped[int | None] = mapped_column(default=None, comment='时长天数, NULL 表示永久')
    auto_renewable: Mapped[bool] = mapped_column(default=False, comment='是否支持自动续费')
    price_cents: Mapped[int] = mapped_column(default=0, comment='价格(分)')
    display_order: Mapped[int] = mapped_column(default=0, comment='显示顺序')
    cover_image: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='封面图')
    description: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='描述')
    sale_period: Mapped[Range[datetime] | None] = mapped_column(TSTZRANGE, default=None, comment='上架时间段')
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        'metadata',
        JSONB,
        default_factory=dict,
        comment='扩展元数据',
    )
    status: Mapped[CommonStatus] = mapped_column(
        PG_ENUM(
            CommonStatus,
            name='common_status',
            create_type=False,
            values_callable=lambda x: _enum_values(CommonStatus),
        ),
        default=CommonStatus.ACTIVE,
        comment='状态',
    )


class TemplatePack(Base):
    """订阅模板与权益包关联表"""

    __tablename__ = 'template_pack'
    __table_args__ = (
        sa.Index('idx_template_pack_template', 'template_id'),
    )

    id: Mapped[id_key] = mapped_column(init=False)
    template_id: Mapped[int] = mapped_column(sa.BigInteger, comment='模板 ID')
    pack_id: Mapped[int] = mapped_column(sa.BigInteger, comment='包 ID')
