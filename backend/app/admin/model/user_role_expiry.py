#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, id_key


class UserRoleExpiry(Base):
    """用户角色有效期表"""

    __tablename__ = 'sys_user_role_expiry'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'role_id', name='uq_sys_user_role_expiry'),
        {'comment': '用户角色有效期表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='用户 ID')
    role_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='角色 ID')
    valid_from: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='有效期开始')
    valid_to: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='有效期结束')
    status: Mapped[int] = mapped_column(default=1, comment='状态(0停用 1正常 2已过期)')
