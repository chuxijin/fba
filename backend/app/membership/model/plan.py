#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UniversalText, id_key


class MembershipPlan(Base):
    """会员计划表"""

    __tablename__ = 'membership_plan'

    id: Mapped[id_key] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(sa.String(64), unique=True, comment='计划名称')
    role_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='关联角色 ID')
    duration_days: Mapped[int] = mapped_column(comment='默认时长天数')
    level: Mapped[int] = mapped_column(default=0, comment='等级层次(0免费 1基础 2高级 3至尊)')
    price: Mapped[int] = mapped_column(default=0, comment='价格(分)')
    original_price: Mapped[int] = mapped_column(default=0, comment='原价(分)')
    description: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='权益描述')
    sort: Mapped[int] = mapped_column(default=0, comment='排序')
    status: Mapped[int] = mapped_column(default=1, comment='状态(0下架 1上架)')
