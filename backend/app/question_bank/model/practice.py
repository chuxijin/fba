#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, TimeZone, UserMixin, id_key
from backend.utils.timezone import timezone

CompatibleJSONB = sa.JSON().with_variant(JSONB, 'postgresql')

if TYPE_CHECKING:
    from .chapter import QuestionChapter
    from .question import Question, QuestionPlacement
    from .user import UserAccount


class PracticeSession(Base, UserMixin):
    """练习会话表"""

    __tablename__ = 'study_practice_session'
    __table_args__ = (
        sa.Index('idx_session_user_status_updated', 'user_id', 'status', 'updated_time'),
        sa.Index('idx_session_user_start_time', 'user_id', 'start_time'),
        sa.Index('idx_session_bank_chapter_status', 'bank_id', 'chapter_id', 'status'),
        sa.Index('idx_session_user_status_source_key', 'user_id', 'status', 'source_key'),
        sa.CheckConstraint(
            "session_type IN ('chapter','bank','random','exam','wrong','favorite','note')",
            name='ck_practice_session_type',
        ),
        sa.CheckConstraint(
            "status IN ('in_progress','completed','abandoned')",
            name='ck_practice_session_status',
        ),
        sa.CheckConstraint(
            'total_count >= 0 AND completed_count >= 0 AND correct_count >= 0 AND wrong_count >= 0',
            name='ck_practice_session_counts_nonneg',
        ),
        sa.CheckConstraint(
            'completed_count <= total_count AND correct_count + wrong_count <= completed_count',
            name='ck_practice_session_counts_logic',
        ),
        sa.CheckConstraint('accuracy_rate >= 0 AND accuracy_rate <= 100', name='ck_practice_session_accuracy'),
        sa.CheckConstraint('total_time >= 0', name='ck_practice_session_time'),
        sa.CheckConstraint(
            '(score IS NULL OR score >= 0) AND (total_score IS NULL OR total_score >= 0)',
            name='ck_practice_session_score',
        ),
        {'comment': '练习会话表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_user_account.user_id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    session_type: Mapped[str] = mapped_column(
        sa.String(32),
        comment='练习类型: chapter/bank/random/exam/wrong/favorite/note',
    )
    bank_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question_bank.id', ondelete='SET NULL'),
        default=None,
        comment='题库 ID',
    )
    chapter_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question_chapter.id', ondelete='SET NULL'),
        default=None,
        comment='章节 ID',
    )
    practice_name: Mapped[str | None] = mapped_column(
        sa.String(255), default=None, comment='练习名称（快照）',
    )
    source_key: Mapped[str | None] = mapped_column(
        sa.String(64), default=None, comment='来源签名',
    )
    source_snapshot: Mapped[dict | None] = mapped_column(
        CompatibleJSONB, default=None, comment='来源快照',
    )
    status: Mapped[str] = mapped_column(
        sa.String(32), default='in_progress', comment='状态: in_progress/completed/abandoned',
    )
    total_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='题目总数')
    completed_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='已完成数量')
    correct_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='答对数量')
    wrong_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='答错数量')
    accuracy_rate: Mapped[Decimal] = mapped_column(
        sa.Numeric(5, 2), default=Decimal('0'), comment='正确率（0-100）',
    )
    score: Mapped[Decimal | None] = mapped_column(sa.Numeric(8, 2), default=None, comment='得分')
    total_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(8, 2), default=None, comment='总分')
    total_time: Mapped[int] = mapped_column(sa.Integer, default=0, comment='总用时（秒）')
    start_time: Mapped[datetime] = mapped_column(
        TimeZone, default_factory=timezone.now, comment='开始时间',
    )
    submit_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='提交时间')
    exam_config: Mapped[dict | None] = mapped_column(CompatibleJSONB, default=None, comment='考试配置')
    del_flag: Mapped[bool] = mapped_column(default=False, comment='删除标志（False 存在 True 删除）')

    # ============ 关系 ============
    account: Mapped[UserAccount] = relationship(init=False, back_populates='practice_sessions', lazy='noload')
    chapter: Mapped['QuestionChapter | None'] = relationship(init=False, lazy='noload')
    session_questions: Mapped[list[SessionQuestion]] = relationship(
        init=False,
        back_populates='session',
        lazy='noload',
        cascade='all, delete-orphan',
    )
    records: Mapped[list[PracticeRecord]] = relationship(
        init=False,
        back_populates='session',
        lazy='noload',
        cascade='all, delete-orphan',
    )


class SessionQuestion(Base):
    """会话题目明细表"""

    __tablename__ = 'study_session_question'
    __table_args__ = (
        sa.UniqueConstraint('session_id', 'seq_no', name='uq_session_question_seq'),
        sa.UniqueConstraint('session_id', 'question_id', name='uq_session_question_question'),
        sa.Index('idx_session_question_question', 'question_id'),
        sa.Index('idx_session_question_placement', 'placement_id'),
        sa.CheckConstraint('seq_no > 0', name='ck_session_question_seq'),
        sa.CheckConstraint(
            "question_type IN ('single','multiple','judgement','fill','shortAnswer')",
            name='ck_session_question_type',
        ),
        sa.CheckConstraint('full_score >= 0', name='ck_session_question_score'),
        {'comment': '会话题目明细表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    session_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_practice_session.id', ondelete='CASCADE'),
        comment='会话 ID',
    )
    question_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question.id', ondelete='CASCADE'),
        comment='题目 ID',
    )
    placement_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question_placement.id', ondelete='RESTRICT'),
        comment='挂载 ID',
    )
    seq_no: Mapped[int] = mapped_column(sa.Integer, comment='题目在会话中的顺序（从 1 开始）')
    question_type: Mapped[str] = mapped_column(
        sa.String(16), comment='题型: single/multiple/judgement/fill/shortAnswer',
    )
    full_score: Mapped[Decimal] = mapped_column(
        sa.Numeric(8, 2), default=Decimal('0'), comment='满分',
    )

    # ============ 关系 ============
    session: Mapped[PracticeSession] = relationship(init=False, back_populates='session_questions', lazy='noload')
    question: Mapped[Question] = relationship(init=False, lazy='noload')
    placement: Mapped[QuestionPlacement] = relationship(init=False, lazy='noload')


class PracticeRecord(Base):
    """答题记录表"""

    __tablename__ = 'study_practice_record'
    __table_args__ = (
        sa.UniqueConstraint('session_id', 'question_id', name='uq_practice_record_session_question'),
        sa.Index('idx_practice_record_session_seq', 'session_id', 'seq_no'),
        sa.Index('idx_practice_record_user_time', 'user_id', 'created_time'),
        sa.Index('idx_practice_record_question_correct', 'question_id', 'is_correct'),
        sa.Index('idx_practice_record_placement_question', 'placement_id', 'question_id'),
        sa.CheckConstraint('seq_no > 0', name='ck_practice_record_seq'),
        sa.CheckConstraint('answer_time >= 0', name='ck_practice_record_time'),
        sa.CheckConstraint('full_score >= 0 AND (score IS NULL OR score >= 0)', name='ck_practice_record_score'),
        {'comment': '答题记录表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    session_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_practice_session.id', ondelete='CASCADE'),
        comment='练习会话 ID',
    )
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_user_account.user_id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    question_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question.id', ondelete='CASCADE'),
        comment='题目 ID',
    )
    placement_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question_placement.id', ondelete='RESTRICT'),
        comment='挂载 ID（避免多挂载歧义）',
    )
    seq_no: Mapped[int] = mapped_column(sa.Integer, comment='题目在会话中的顺序（从 1 开始）')
    user_answer: Mapped[dict | list | str] = mapped_column(CompatibleJSONB, comment='用户答案')
    is_correct: Mapped[bool | None] = mapped_column(default=None, comment='是否正确（提交前可空）')
    score: Mapped[Decimal | None] = mapped_column(sa.Numeric(8, 2), default=None, comment='得分')
    full_score: Mapped[Decimal] = mapped_column(sa.Numeric(8, 2), default=Decimal('0'), comment='满分')
    answer_time: Mapped[int] = mapped_column(sa.Integer, default=0, comment='本题用时（秒）')
    judged_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='判题时间')
    judge_version: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='判题规则版本')

    # ============ 关系 ============
    account: Mapped[UserAccount] = relationship(init=False, back_populates='practice_records', lazy='noload')
    session: Mapped[PracticeSession] = relationship(init=False, back_populates='records', lazy='noload')
    question: Mapped[Question] = relationship(init=False, lazy='noload')
    placement: Mapped[QuestionPlacement] = relationship(init=False, lazy='noload')


class WrongQuestionBook(Base, UserMixin):
    """错题本表"""

    __tablename__ = 'study_wrong_question_book'
    __table_args__ = (
        # partial unique index: 按题目归并（无挂载）
        sa.Index(
            'uq_wrong_book_user_question_when_no_placement',
            'user_id', 'question_id',
            unique=True,
            postgresql_where=sa.text('placement_id IS NULL'),
        ),
        # partial unique index: 按挂载区分
        sa.Index(
            'uq_wrong_book_user_question_placement',
            'user_id', 'question_id', 'placement_id',
            unique=True,
            postgresql_where=sa.text('placement_id IS NOT NULL'),
        ),
        sa.Index('idx_wrong_book_user_mastered_pinned_updated', 'user_id', 'is_mastered', 'is_pinned', 'updated_time'),
        sa.Index('idx_wrong_book_question', 'question_id'),
        sa.Index('idx_wrong_book_placement', 'placement_id'),
        sa.CheckConstraint('wrong_count >= 0 AND correct_streak >= 0', name='ck_wrong_book_counts'),
        {'comment': '错题本表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_user_account.user_id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    question_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question.id', ondelete='CASCADE'),
        comment='题目 ID',
    )
    placement_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question_placement.id', ondelete='SET NULL'),
        default=None,
        comment='挂载 ID（可选，区分题库来源）',
    )
    wrong_count: Mapped[int] = mapped_column(sa.Integer, default=1, comment='错误次数')
    correct_streak: Mapped[int] = mapped_column(sa.Integer, default=0, comment='连续做对次数')
    first_wrong_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='首次错误时间')
    last_wrong_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最后一次错误时间')
    last_practice_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最后一次练习时间')
    is_mastered: Mapped[bool] = mapped_column(default=False, comment='是否已掌握')
    mastered_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='掌握时间')
    is_pinned: Mapped[bool] = mapped_column(default=False, comment='是否置顶')
    pinned_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='置顶时间')

    # ============ 关系 ============
    account: Mapped[UserAccount] = relationship(init=False, back_populates='wrong_questions', lazy='noload')
    question: Mapped[Question] = relationship(init=False, lazy='noload')
    placement: Mapped[QuestionPlacement | None] = relationship(init=False, lazy='noload')

    @property
    def question_stem(self) -> str | None:
        if self.question:
            return self.question.stem
        return None

    @property
    def question_type(self) -> str | None:
        if self.question:
            return self.question.type
        return None

    @property
    def bank_id(self) -> int | None:
        if self.placement:
            return self.placement.bank_id
        return None

    @property
    def bank_name(self) -> str | None:
        if self.placement and self.placement.bank:
            return self.placement.bank.name
        return None

    @property
    def chapter_id(self) -> int | None:
        if self.placement:
            return self.placement.chapter_id
        return None

    @property
    def chapter_name(self) -> str | None:
        if self.placement and self.placement.chapter:
            return self.placement.chapter.name
        return None

    @property
    def cat_id(self) -> int | None:
        if self.placement and self.placement.bank:
            return self.placement.bank.cat_id
        return None

    @property
    def cat_name(self) -> str | None:
        if self.placement and self.placement.bank and self.placement.bank.category:
            return self.placement.bank.category.name
        return None
