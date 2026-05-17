#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM, JSONB, TSTZRANGE
from sqlalchemy.dialects.postgresql.ranges import Range
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.access.constants import SubscriptionSource, SubscriptionStatus
from backend.common.model import Base, id_key


def _enum_values(enum_cls: type) -> list[str]:
    """ENUM values_callable 工具"""
    return [member.value for member in enum_cls]


class Subscription(Base):
    """用户订阅流水表"""

    __tablename__ = 'subscription'

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, comment='用户 ID')
    template_id: Mapped[int] = mapped_column(sa.BigInteger, comment='模板 ID')
    valid_period: Mapped[Range[datetime]] = mapped_column(TSTZRANGE, comment='有效时间段')
    source: Mapped[SubscriptionSource] = mapped_column(
        PG_ENUM(
            SubscriptionSource,
            name='subscription_source',
            create_type=False,
            values_callable=lambda x: _enum_values(SubscriptionSource),
        ),
        comment='来源',
    )
    status: Mapped[SubscriptionStatus] = mapped_column(
        PG_ENUM(
            SubscriptionStatus,
            name='subscription_status',
            create_type=False,
            values_callable=lambda x: _enum_values(SubscriptionStatus),
        ),
        default=SubscriptionStatus.ACTIVE,
        comment='状态',
    )
    source_ref: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='来源引用')
    parent_subscription_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, default=None, comment='父订阅 ID(续费链/赠送链)'
    )
    cancel_reason: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='取消原因')
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        'metadata',
        JSONB,
        default_factory=dict,
        comment='扩展元数据',
    )
