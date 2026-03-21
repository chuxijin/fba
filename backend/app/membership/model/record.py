#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, UniversalText, id_key


class MembershipRecord(Base):
    """会员变动记录表"""

    __tablename__ = 'membership_record'

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='用户 ID')
    plan_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='会员计划 ID')
    days: Mapped[int] = mapped_column(comment='变动天数(正数增加 负数扣减)')
    source: Mapped[str] = mapped_column(sa.String(32), comment='来源标识')
    source_detail: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='来源详情')
    valid_to_before: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='变动前到期时间')
    valid_to_after: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='变动后到期时间')
    remark: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='备注')
