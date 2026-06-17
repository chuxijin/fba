#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM, JSONB, TSTZRANGE
from sqlalchemy.dialects.postgresql.ranges import Range
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.access.constants import CommonStatus, GrantMode
from backend.common.model import Base, id_key


def _enum_values(enum_cls: type) -> list[str]:
    """ENUM values_callable 工具"""
    return [member.value for member in enum_cls]


class ResourceRule(Base):
    """资源↔权益绑定规则表"""

    __tablename__ = 'resource_rule'

    id: Mapped[id_key] = mapped_column(init=False)
    resource_type: Mapped[str] = mapped_column(sa.String(32), comment='资源类型')
    resource_id: Mapped[int] = mapped_column(sa.BigInteger, comment='资源 ID')
    entitlement_code: Mapped[str] = mapped_column(sa.String(64), comment='权益编码')
    grant_mode: Mapped[GrantMode] = mapped_column(
        PG_ENUM(
            GrantMode,
            name='grant_mode',
            create_type=False,
            values_callable=lambda x: _enum_values(GrantMode),
        ),
        comment='授权模式',
    )
    priority: Mapped[int] = mapped_column(default=0, comment='优先级(越大越优先)')
    valid_period: Mapped[Range[datetime] | None] = mapped_column(
        TSTZRANGE, default=None, comment='生效时间段, NULL 表示永久'
    )
    audience_filter: Mapped[dict[str, Any]] = mapped_column(JSONB, default_factory=dict, comment='受众过滤条件')
    inherit_to_children: Mapped[bool] = mapped_column(default=True, comment='是否级联到子资源')
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
