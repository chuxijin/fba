#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM, JSONB, TSTZRANGE
from sqlalchemy.dialects.postgresql.ranges import Range
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.access.constants import CommonStatus, GrantSource
from backend.common.model import DataClassBase, TimeZone, id_key
from backend.utils.timezone import timezone


def _enum_values(enum_cls: type) -> list[str]:
    """ENUM values_callable 工具"""
    return [member.value for member in enum_cls]


class DirectGrant(DataClassBase):
    """直接授予表(运营补偿/活动赠送)"""

    __tablename__ = 'direct_grant'

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, comment='用户 ID')
    entitlement_code: Mapped[str] = mapped_column(sa.String(64), comment='权益编码')
    valid_period: Mapped[Range[datetime]] = mapped_column(TSTZRANGE, comment='有效时间段')
    source: Mapped[GrantSource] = mapped_column(
        PG_ENUM(
            GrantSource,
            name='grant_source',
            create_type=False,
            values_callable=lambda x: _enum_values(GrantSource),
        ),
        comment='授予来源',
    )
    value_int: Mapped[int | None] = mapped_column(default=None, comment='附带数值')
    value_meta: Mapped[dict[str, Any]] = mapped_column(JSONB, default_factory=dict, comment='扩展参数')
    source_ref: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='来源引用')
    reason: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='授予原因')
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
    created_time: Mapped[datetime] = mapped_column(
        TimeZone,
        init=False,
        default_factory=timezone.now,
        comment='创建时间',
    )
