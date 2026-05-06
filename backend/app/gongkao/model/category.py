#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UserMixin, id_key


class GkCategory(Base, UserMixin):
    """公考分类表"""

    __tablename__ = 'gk_category'
    __table_args__ = (
        sa.UniqueConstraint('name', 'type', name='uq_category_name_type'),
        {'comment': '公考分类表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)

    # 基础信息（必填字段）
    name: Mapped[str] = mapped_column(sa.String(50), index=True, comment='分类名称')
    type: Mapped[str] = mapped_column(sa.String(20), index=True, comment='分类类型')

    # 基础信息（可选字段）
    parent_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, index=True, comment='父级分类 ID')
    description: Mapped[str | None] = mapped_column(sa.String(200), default=None, comment='分类描述')
    icon: Mapped[str | None] = mapped_column(sa.String(50), default=None, comment='图标')
    color: Mapped[str | None] = mapped_column(sa.String(20), default=None, comment='颜色标识')
    sort_order: Mapped[int] = mapped_column(default=0, comment='排序权重')
    status: Mapped[bool] = mapped_column(default=True, comment='状态')
