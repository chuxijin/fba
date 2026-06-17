#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.access.constants import LedgerOperation
from backend.common.model import DataClassBase, TimeZone, id_key
from backend.utils.timezone import timezone


def _enum_values(enum_cls: type) -> list[str]:
    """ENUM values_callable 工具"""
    return [member.value for member in enum_cls]


class QuotaLedger(DataClassBase):
    """配额账本表(事件溯源, append-only)"""

    __tablename__ = 'quota_ledger'
    __table_args__ = (
        sa.Index(
            'idx_quota_ledger_user_scope_cycle',
            'user_id',
            'entitlement_code',
            'scope_key',
            'cycle_key',
            'occurred_at',
            'id',
        ),
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, comment='用户 ID')
    entitlement_code: Mapped[str] = mapped_column(sa.String(64), comment='权益编码')
    cycle_type: Mapped[str] = mapped_column(sa.String(16), comment='周期类型')
    cycle_key: Mapped[str] = mapped_column(sa.String(32), comment='周期键')
    operation: Mapped[LedgerOperation] = mapped_column(
        PG_ENUM(
            LedgerOperation,
            name='ledger_op',
            create_type=False,
            values_callable=lambda x: _enum_values(LedgerOperation),
        ),
        comment='操作类型',
    )
    amount: Mapped[int] = mapped_column(comment='变动数量(始终为正)')
    balance_after: Mapped[int] = mapped_column(comment='操作后余额(快照)')
    source: Mapped[str] = mapped_column(sa.String(32), comment='来源标识')
    scope_key: Mapped[str] = mapped_column(sa.String(64), default='global', comment='业务范围键')
    source_ref: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='来源引用')
    idempotency_key: Mapped[str | None] = mapped_column(sa.String(128), unique=True, default=None, comment='幂等键')
    reason: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='原因')
    occurred_at: Mapped[datetime] = mapped_column(
        TimeZone,
        init=False,
        default_factory=timezone.now,
        comment='发生时间',
    )
