#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, id_key


class BiliAccount(Base):
    """B 站账号表"""

    __tablename__ = 'bili_account'

    id: Mapped[id_key] = mapped_column(init=False)
    account_name: Mapped[str] = mapped_column(sa.String(128), index=True, comment='账号名称')
    mid: Mapped[str | None] = mapped_column(sa.String(64), default=None, unique=True, index=True, comment='B 站用户 MID')
    cookie: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='登录凭证（加密存储）')
    ip: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='使用 IP')
    status: Mapped[int] = mapped_column(default=1, index=True, comment='状态(0 停用 1 正常)')
    remark: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='备注')
    last_active_time: Mapped[datetime | None] = mapped_column(
        TimeZone, init=False, default=None, comment='最后活跃时间'
    )

    # 逻辑外键
    category_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, index=True, comment='分类关联 ID')
