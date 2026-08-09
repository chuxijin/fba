#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.access.constants import CommonStatus
from backend.common.model import Base, TimeZone, id_key
from backend.utils.timezone import timezone


def _enum_values(enum_cls: type) -> list[str]:
    """ENUM values_callable 工具"""
    return [member.value for member in enum_cls]


class QuotaGrant(Base):
    """配额额度包表(配额余额的唯一真相源)

    一个用户在同一权益编码下可同时持有多个额度包, 例如:
    - 订阅周期补账包(source=subscription, expires_at=周期末)
    - 活动赠送的一次性包(source=activity, expires_at=NULL 表示永不过期)

    扣减时按 expires_at 升序跨包消耗, 即"优先扣即将失效的配额";
    余额为当前所有有效包 remaining_amount 之和, 不再按周期分桶。
    """

    __tablename__ = 'quota_grant'
    __table_args__ = (
        sa.Index('idx_quota_grant_lookup', 'user_id', 'entitlement_code', 'scope_key', 'status'),
        sa.Index('idx_quota_grant_expires', 'expires_at'),
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, comment='用户 ID')
    entitlement_code: Mapped[str] = mapped_column(sa.String(64), comment='权益编码')
    granted_amount: Mapped[int] = mapped_column(comment='发放总量')
    remaining_amount: Mapped[int] = mapped_column(comment='剩余可用量')
    source: Mapped[str] = mapped_column(sa.String(32), comment='额度来源')
    scope_key: Mapped[str] = mapped_column(sa.String(64), default='global', comment='业务范围键')
    effective_at: Mapped[datetime] = mapped_column(
        TimeZone,
        default_factory=timezone.now,
        comment='生效时间',
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        TimeZone,
        default=None,
        comment='过期时间, NULL 表示永不过期',
    )
    priority: Mapped[int] = mapped_column(default=0, comment='扣减优先级(同过期时间时越大越先扣)')
    cycle_type: Mapped[str | None] = mapped_column(sa.String(16), default=None, comment='来源周期类型')
    cycle_key: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='来源周期键')
    source_ref: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='来源引用')
    idempotency_key: Mapped[str | None] = mapped_column(
        sa.String(128),
        unique=True,
        default=None,
        comment='幂等键',
    )
    reason: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='发放原因')
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
