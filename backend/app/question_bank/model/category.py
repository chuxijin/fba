#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, id_key

if TYPE_CHECKING:
    from .bank import QuestionBank


class ExamCategory(Base):
    """考试分类表"""

    __tablename__ = 'study_exam_category'
    __table_args__ = (
        sa.UniqueConstraint('code', name='uq_study_exam_category_code'),
        sa.Index('idx_study_exam_category_parent_sort', 'parent_id', 'sort_order'),
        {'comment': '考试分类表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(sa.String(64), comment='分类名称')
    cat_type: Mapped[int] = mapped_column(
        sa.SmallInteger,
        comment='分类类型（0=全部 1=题库 2=词库 3=资料包 4=商城）',
    )
    code: Mapped[str] = mapped_column(sa.String(32), comment='分类编码')
    parent_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_exam_category.id', ondelete='SET NULL'),
        default=None,
        comment='父级分类 ID',
    )
    level: Mapped[int] = mapped_column(sa.SmallInteger, default=1, comment='分类层级')
    is_active: Mapped[bool] = mapped_column(default=True, comment='是否启用')
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='排序权重')

    parent: Mapped['ExamCategory | None'] = relationship(
        init=False,
        remote_side=lambda: [ExamCategory.id],
        back_populates='children',
        lazy='noload',
    )
    children: Mapped[list['ExamCategory']] = relationship(
        init=False,
        back_populates='parent',
        cascade='all, delete-orphan',
        single_parent=True,
        lazy='noload',
    )
    banks: Mapped[list['QuestionBank']] = relationship(init=False, back_populates='category', lazy='noload')
