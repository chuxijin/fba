#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class FoodCategory(Base):
    """食物分类表"""

    __tablename__ = 'health_food_category'

    id: Mapped[id_key] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(sa.String(64), comment='分类名称')
    parent_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, index=True, comment='父分类 ID')
    sort: Mapped[int] = mapped_column(default=0, comment='排序')
    icon: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='分类图标')
    description: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='分类描述')
    status: Mapped[int] = mapped_column(default=1, comment='状态(0停用 1正常)')
    del_flag: Mapped[bool] = mapped_column(default=False, comment='删除标志(0删除 1存在)')
