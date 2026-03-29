#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UniversalText, id_key


class MembershipEntitlement(Base):
    """会员权益定义表"""

    __tablename__ = 'membership_entitlement'
    __table_args__ = (
        sa.UniqueConstraint('code', name='uq_membership_entitlement_code'),
        sa.Index('idx_membership_entitlement_status_sort', 'status', 'sort'),
        {'comment': '会员权益定义表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    code: Mapped[str] = mapped_column(sa.String(64), comment='权益编码')
    name: Mapped[str] = mapped_column(sa.String(64), comment='权益名称')
    value_type: Mapped[str] = mapped_column(sa.String(16), default='bool', comment='权益值类型')
    default_value: Mapped[int] = mapped_column(default=0, comment='默认值')
    sort: Mapped[int] = mapped_column(default=0, comment='排序')
    status: Mapped[int] = mapped_column(default=1, comment='状态(0停用 1启用)')
    description: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='描述')
