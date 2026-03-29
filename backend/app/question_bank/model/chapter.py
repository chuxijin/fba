#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, id_key

if TYPE_CHECKING:
    from .bank import QuestionBank
    from .question import QuestionPlacement


class QuestionChapter(Base):
    """题库章节表"""

    __tablename__ = 'study_question_chapter'
    __table_args__ = (
        sa.UniqueConstraint('bank_id', 'code', name='uq_study_question_chapter_code'),
        sa.UniqueConstraint('bank_id', 'parent_id', 'name', name='uq_study_question_chapter_name'),
        sa.Index(
            'uq_study_question_chapter_root_name',
            'bank_id',
            'name',
            unique=True,
            postgresql_where=sa.text('parent_id IS NULL'),
        ),
        sa.Index('idx_study_question_chapter_parent_sort', 'bank_id', 'parent_id', 'sort_order'),
        {'comment': '题库章节表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    bank_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question_bank.id', ondelete='CASCADE'),
        comment='题库 ID',
    )
    name: Mapped[str] = mapped_column(sa.String(128), comment='章节名称')
    parent_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question_chapter.id', ondelete='SET NULL'),
        default=None,
        comment='父级章节 ID',
    )
    code: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='章节编码')
    level: Mapped[int] = mapped_column(sa.SmallInteger, default=1, comment='章节层级')
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='排序权重')
    q_count_cache: Mapped[int] = mapped_column(sa.Integer, default=0, comment='缓存题量')
    status: Mapped[int] = mapped_column(sa.SmallInteger, default=1, comment='状态')

    bank: Mapped['QuestionBank'] = relationship(init=False, back_populates='chapters', lazy='selectin')
    parent: Mapped['QuestionChapter | None'] = relationship(
        init=False,
        remote_side=lambda: [QuestionChapter.id],
        back_populates='children',
        lazy='noload',
    )
    children: Mapped[list['QuestionChapter']] = relationship(
        init=False,
        back_populates='parent',
        cascade='all, delete-orphan',
        single_parent=True,
        lazy='noload',
    )
    placements: Mapped[list['QuestionPlacement']] = relationship(
        init=False,
        back_populates='chapter',
        lazy='noload',
    )
