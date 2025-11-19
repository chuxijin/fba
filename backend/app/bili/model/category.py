#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class BiliCategory(Base):
    """B 站内容分类表"""

    __tablename__ = 'bili_category'

    id: Mapped[id_key] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(sa.String(64), unique=True, index=True, comment='分类名称')
    description: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='分类描述')
    sort: Mapped[int] = mapped_column(default=0, comment='排序')
    status: Mapped[int] = mapped_column(default=1, index=True, comment='状态(0 停用 1 正常)')

    # 逻辑外键
    parent_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, index=True, comment='父分类 ID')
