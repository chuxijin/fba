#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.access.constants import DecisionKind
from backend.common.model import DataClassBase, TimeZone
from backend.utils.timezone import timezone


def _enum_values(enum_cls: type) -> list[str]:
    """ENUM values_callable 工具"""
    return [member.value for member in enum_cls]


class DecisionLog(DataClassBase):
    """决策审计日志表(按 occurred_at 月分区)"""

    __tablename__ = 'decision_log'

    id: Mapped[int] = mapped_column(sa.BigInteger, primary_key=True, init=False, autoincrement=True)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, comment='用户 ID')
    resource_type: Mapped[str] = mapped_column(sa.String(32), comment='资源类型')
    resource_id: Mapped[int] = mapped_column(sa.BigInteger, comment='资源 ID')
    action: Mapped[str] = mapped_column(sa.String(32), comment='动作')
    decision: Mapped[DecisionKind] = mapped_column(
        PG_ENUM(
            DecisionKind,
            name='decision_kind',
            create_type=False,
            values_callable=lambda x: _enum_values(DecisionKind),
        ),
        comment='决策结果',
    )
    reason_code: Mapped[str] = mapped_column(sa.String(32), comment='原因码')
    matched_grant: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='匹配的权益编码')
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, default_factory=dict, comment='上下文快照')
    occurred_at: Mapped[datetime] = mapped_column(
        TimeZone,
        primary_key=True,
        init=False,
        default_factory=timezone.now,
        comment='决策时间',
    )
