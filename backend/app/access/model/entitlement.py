#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.access.constants import CommonStatus, EntitlementCategory
from backend.common.model import Base, id_key


def _enum_values(enum_cls: type) -> list[str]:
    """ENUM values_callable 工具"""
    return [member.value for member in enum_cls]


class Entitlement(Base):
    """权益字典表

    权益是最细粒度的能力凭证, 由运营自由勾选组合进权益包售卖。
    """

    __tablename__ = 'entitlement'

    id: Mapped[id_key] = mapped_column(init=False)
    code: Mapped[str] = mapped_column(sa.String(64), unique=True, comment='权益编码')
    name: Mapped[str] = mapped_column(sa.String(128), comment='权益名')
    category: Mapped[EntitlementCategory] = mapped_column(
        PG_ENUM(
            EntitlementCategory,
            name='entitlement_category',
            create_type=False,
            values_callable=lambda x: _enum_values(EntitlementCategory),
        ),
        comment='权益分类',
    )
    domain_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='所属领域 ID')
    resource_type: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='资源类型')
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
