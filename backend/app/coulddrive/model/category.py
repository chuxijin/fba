#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Optional

from sqlalchemy import String, Integer, Boolean, Text, Index, UniqueConstraint, ForeignKey, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, UserMixin, id_key


class Category(Base, UserMixin):
    """分类表"""

    __tablename__ = 'yp_category'

    id: Mapped[id_key] = mapped_column(init=False)
    
    # 必填字段（无默认值）
    name: Mapped[str] = mapped_column(String(100), comment='分类名称')
    code: Mapped[str] = mapped_column(String(50), comment='分类编码')
    category_type: Mapped[str] = mapped_column(String(50), comment='分类类型(domain-领域, subject-科目, resource_type-资源类型)')
    level: Mapped[int] = mapped_column(Integer, comment='分类层级')
    path: Mapped[str] = mapped_column(String(500), comment='分类路径')
    
    # 可选字段（有默认值）
    description: Mapped[str | None] = mapped_column(Text, default=None, comment='分类描述')
    sort: Mapped[int] = mapped_column(Integer, default=0, comment='排序值')
    status: Mapped[int] = mapped_column(Integer, default=1, comment='状态(0停用 1正常)')
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, comment='是否系统分类')

    # 父级分类一对多（完全参照menu.py的写法）
    parent_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey('yp_category.id', ondelete='SET NULL'), default=None, index=True, comment='父分类ID'
    )
    parent: Mapped[Optional['Category']] = relationship(init=False, back_populates='children', remote_side=[id])
    children: Mapped[Optional[list['Category']]] = relationship(init=False, back_populates='parent')
    
    # 索引和约束（简化）
    __table_args__ = (
        UniqueConstraint('code', name='uk_category_code'),
    ) 