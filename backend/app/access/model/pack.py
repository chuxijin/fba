#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.access.constants import CommonStatus, GradeLevel
from backend.common.model import Base, id_key


def _enum_values(enum_cls: type) -> list[str]:
    """ENUM values_callable 工具"""
    return [member.value for member in enum_cls]


class EntitlementPack(Base):
    """权益包表"""

    __tablename__ = 'entitlement_pack'

    id: Mapped[id_key] = mapped_column(init=False)
    code: Mapped[str] = mapped_column(sa.String(64), unique=True, comment='包编码')
    name: Mapped[str] = mapped_column(sa.String(128), comment='包名称')
    grade: Mapped[GradeLevel] = mapped_column(
        PG_ENUM(
            GradeLevel,
            name='grade_level',
            create_type=False,
            values_callable=lambda x: _enum_values(GradeLevel),
        ),
        default=GradeLevel.STANDARD,
        comment='档次',
    )
    domain_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='所属领域 ID')
    description: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='描述')
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


class PackItem(Base):
    """权益包成员表"""

    __tablename__ = 'pack_item'
    __table_args__ = (
        sa.Index('idx_pack_item_pack_status', 'pack_id', 'status'),
    )

    id: Mapped[id_key] = mapped_column(init=False)
    pack_id: Mapped[int] = mapped_column(sa.BigInteger, comment='包 ID')
    entitlement_id: Mapped[int] = mapped_column(sa.BigInteger, comment='权益 ID')
    value_int: Mapped[int | None] = mapped_column(default=None, comment='整数值(配额上限)')
    value_meta: Mapped[dict] = mapped_column(JSONB, default_factory=dict, comment='扩展参数')
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
