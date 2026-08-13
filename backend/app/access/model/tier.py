#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.access.constants import CommonStatus
from backend.common.model import Base, id_key


class MembershipTier(Base):
    """商业会员档位表

    档位负责售卖展示、排序和会员身份识别；具体功能准入仍由权益包中的
    entitlement_code 决定，禁止使用档位权重替代权益鉴权。
    """

    __tablename__ = 'membership_tier'

    id: Mapped[id_key] = mapped_column(init=False)
    code: Mapped[str] = mapped_column(sa.String(32), unique=True, comment='档位编码')
    name: Mapped[str] = mapped_column(sa.String(64), comment='档位名称')
    weight: Mapped[int] = mapped_column(default=0, comment='展示排序权重')
    is_paid: Mapped[bool] = mapped_column(default=False, comment='是否属于付费会员')
    badge_color: Mapped[str | None] = mapped_column(sa.String(16), default=None, comment='徽章主题色')
    description: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='描述')
    display_order: Mapped[int] = mapped_column(default=0, comment='显示顺序')
    metadata_: Mapped[dict] = mapped_column(
        'metadata',
        JSONB,
        default_factory=dict,
        comment='扩展展示配置',
    )
    status: Mapped[CommonStatus] = mapped_column(
        PG_ENUM(
            CommonStatus,
            name='common_status',
            create_type=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        default=CommonStatus.ACTIVE,
        comment='状态',
    )
