#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, UserMixin, id_key

if TYPE_CHECKING:
    from .chapter import QuestionChapter
    from .question import QuestionPlacement


class QuestionBank(Base, UserMixin):
    """刷题内容表"""

    __tablename__ = 'study_question_bank'
    __table_args__ = (
        sa.UniqueConstraint('code', name='uq_study_question_bank_code'),
        sa.Index('idx_study_question_bank_category_status', 'cat_id', 'status'),
        sa.Index('idx_study_question_bank_parent_sort', 'parent_id', 'sort_order'),
        sa.Index('idx_study_question_bank_chapter_source', 'chapter_source_bank_id'),
        sa.Index('idx_study_question_bank_type_scene_status', 'bank_type', 'scene_mask', 'status'),
        {'comment': '刷题内容表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    cat_id: Mapped[int] = mapped_column(sa.BigInteger, comment='分类 ID')
    name: Mapped[str] = mapped_column(sa.String(128), comment='内容名称')
    code: Mapped[str] = mapped_column(sa.String(32), comment='业务编码')
    owner_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_user_account.user_id', ondelete='CASCADE'),
        default=None,
        comment='所属用户 ID（NULL 表示公共题库）',
    )
    desc: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='描述')
    year: Mapped[int | None] = mapped_column(
        sa.SmallInteger,
        default=None,
        comment='年份（试卷用）',
    )
    cover_url: Mapped[str | None] = mapped_column(sa.String(255), default=None, comment='封面地址')
    difficulty: Mapped[Decimal | None] = mapped_column(sa.Numeric(3, 1), default=None, comment='整体难度')
    bank_type: Mapped[int] = mapped_column(
        sa.SmallInteger,
        default=1,
        comment='内容类型: 1=习题, 2=试卷, 3=合集',
    )
    scene_mask: Mapped[int] = mapped_column(
        sa.Integer,
        default=1,
        comment='可用场景位标记: 1=练习, 2=考试, 4=模考, 8=错题重练',
    )
    parent_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question_bank.id', ondelete='SET NULL'),
        default=None,
        comment='父合集 ID',
    )
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='排序权重')
    chapter_source_bank_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question_bank.id', ondelete='RESTRICT'),
        default=None,
        comment='篇章来源内容 ID',
    )
    status: Mapped[int] = mapped_column(sa.SmallInteger, default=1, comment='状态')
    q_count_cache: Mapped[int] = mapped_column(sa.Integer, default=0, comment='缓存题量')
    total_score_cache: Mapped[Decimal] = mapped_column(
        sa.Numeric(8, 2),
        default=Decimal('0'),
        comment='缓存总分',
    )
    buy_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='购买数量')

    parent: Mapped['QuestionBank | None'] = relationship(
        init=False,
        remote_side=lambda: [QuestionBank.id],
        back_populates='children',
        foreign_keys=lambda: [QuestionBank.parent_id],
        lazy='noload',
    )
    children: Mapped[list['QuestionBank']] = relationship(
        init=False,
        back_populates='parent',
        cascade='all, delete-orphan',
        single_parent=True,
        foreign_keys=lambda: [QuestionBank.parent_id],
        lazy='noload',
    )
    chapters: Mapped[list['QuestionChapter']] = relationship(
        init=False,
        back_populates='bank',
        cascade='all, delete-orphan',
        lazy='noload',
    )
    placements: Mapped[list['QuestionPlacement']] = relationship(
        init=False,
        back_populates='bank',
        cascade='all, delete-orphan',
        lazy='noload',
    )
