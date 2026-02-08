#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, id_key

if TYPE_CHECKING:
    from .chapter import QuestionChapter
    from .question import Question


class QuestionBank(Base):
    """题库表"""

    __tablename__ = 'study_question_bank'
    __table_args__ = (
        sa.UniqueConstraint('code', name='uq_study_question_bank_code'),
        sa.Index('idx_study_question_bank_category_status', 'cat_id', 'status'),
        sa.Index('idx_study_question_bank_parent', 'parent_id'),
        {'comment': '题库表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    cat_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        index=True,
        comment='所属分类 ID（关联 sys_category）',
    )
    name: Mapped[str] = mapped_column(sa.String(128), comment='题库名称')
    code: Mapped[str] = mapped_column(sa.String(32), comment='题库编码')
    desc: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='题库描述')
    cover_url: Mapped[str | None] = mapped_column(sa.String(255), default=None, comment='封面地址')
    difficulty: Mapped[Decimal | None] = mapped_column(sa.Numeric(3, 1), default=None, comment='难度')
    type: Mapped[int] = mapped_column(
        sa.SmallInteger,
        default=10,
        comment='类型: 10=题库(含题目), 20=合集(含子题库)',
    )
    parent_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question_bank.id', ondelete='SET NULL'),
        default=None,
        comment='父级题库 ID',
    )
    status: Mapped[int] = mapped_column(sa.SmallInteger, default=1, index=True, comment='题库状态')
    scope: Mapped[int] = mapped_column(sa.SmallInteger, default=1, comment='可见范围')
    q_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='题目数量')
    total_score: Mapped[Decimal] = mapped_column(sa.Numeric(8, 2), default=Decimal('0'), comment='题库总分')
    buy_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='购买数量')

    parent: Mapped['QuestionBank | None'] = relationship(
        init=False,
        remote_side=lambda: [QuestionBank.id],
        back_populates='children',
        lazy='selectin',
    )
    children: Mapped[list['QuestionBank']] = relationship(
        init=False,
        back_populates='parent',
        cascade='all, delete-orphan',
        single_parent=True,
        lazy='noload',
    )
    chapters: Mapped[list['QuestionChapter']] = relationship(init=False, back_populates='bank', cascade='all, delete-orphan', lazy='noload')
    questions: Mapped[list['Question']] = relationship(init=False, back_populates='bank', cascade='all, delete-orphan', lazy='noload')
