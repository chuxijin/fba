from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, TimeZone, id_key
from backend.utils.timezone import timezone

from .common import CompatibleJSONB

if TYPE_CHECKING:
    from .asset import QbQuestionAttemptAsset
    from .evaluation import QbEvaluationRun
    from .question import QbQuestion


class QbPracticeSession(Base):
    """One delivered practice or exam session pinned to a bank revision."""

    __tablename__ = 'qbank_v2_practice_session'
    __table_args__ = (
        sa.UniqueConstraint('session_key', 'deleted', name='uq_qbv2_session_key_deleted'),
        sa.UniqueConstraint('user_id', 'id', name='uq_qbv2_session_user_id'),
        sa.CheckConstraint(
            "mode IN ('practice','exam','mock','memorize','review','adaptive')",
            name='ck_qbv2_session_mode',
        ),
        sa.CheckConstraint(
            "source_type IN ('bank','section','knowledge_point','wrong','favorite','note','custom','adaptive')",
            name='ck_qbv2_session_source_type',
        ),
        sa.CheckConstraint(
            "status IN ('created','in_progress','submitted','graded','expired','cancelled')",
            name='ck_qbv2_session_status',
        ),
        sa.CheckConstraint('total_items >= 0', name='ck_qbv2_session_total'),
        sa.CheckConstraint('answered_items >= 0 AND answered_items <= total_items', name='ck_qbv2_session_answered'),
        sa.CheckConstraint('correct_items >= 0 AND correct_items <= answered_items', name='ck_qbv2_session_correct'),
        sa.CheckConstraint('score >= 0', name='ck_qbv2_session_score'),
        sa.Index('ix_qbv2_session_user_status', 'user_id', 'status', 'created_time'),
        sa.Index(
            'ix_qbv2_session_user_created',
            'user_id',
            sa.desc('created_time'),
            sa.desc('id'),
            postgresql_where=sa.text('deleted = 0'),
        ).ddl_if(dialect='postgresql'),
        sa.Index('ix_qbv2_session_bank_revision', 'bank_revision_id', 'status'),
        sa.Index('ix_qbv2_session_user_source', 'user_id', 'source_type', 'created_time'),
        {'comment': '练习与考试会话表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    session_key: Mapped[str] = mapped_column(sa.String(64), comment='对外幂等会话标识')
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='RESTRICT'),
        comment='答题用户 ID',
    )
    bank_revision_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_bank_revision.id', ondelete='RESTRICT'),
        default=None,
        comment='题库版本 ID；自由组题时为空',
    )
    mode: Mapped[str] = mapped_column(sa.String(16), default='practice', comment='会话模式')
    source_type: Mapped[str] = mapped_column(sa.String(24), default='bank', comment='组题来源类型')
    source_ref: Mapped[str | None] = mapped_column(sa.String(160), default=None, comment='来源稳定引用')
    title_snapshot: Mapped[str | None] = mapped_column(sa.String(255), default=None, comment='会话标题快照')
    status: Mapped[str] = mapped_column(sa.String(16), default='created', comment='会话状态')
    started_time: Mapped[datetime] = mapped_column(
        TimeZone,
        default_factory=timezone.now,
        comment='开始时间',
    )
    submitted_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='交卷时间')
    expires_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='会话过期时间')
    total_items: Mapped[int] = mapped_column(sa.Integer, default=0, comment='投递题数快照')
    answered_items: Mapped[int] = mapped_column(sa.Integer, default=0, comment='已答题数缓存')
    correct_items: Mapped[int] = mapped_column(sa.Integer, default=0, comment='答对题数缓存')
    score: Mapped[Decimal] = mapped_column(sa.Numeric(10, 2), default=Decimal('0.00'), comment='当前得分缓存')
    delivery_config: Mapped[dict[str, Any]] = mapped_column(
        CompatibleJSONB,
        default_factory=dict,
        comment='抽题和投递参数快照',
    )
    source_snapshot: Mapped[dict[str, Any]] = mapped_column(
        CompatibleJSONB,
        default_factory=dict,
        comment='章节、知识点、收藏夹等来源快照',
    )

    items: Mapped[list[QbPracticeSessionItem]] = relationship(
        init=False,
        back_populates='session',
        cascade='all, delete-orphan',
        lazy='noload',
    )
    attempts: Mapped[list[QbQuestionAttempt]] = relationship(
        init=False,
        back_populates='session',
        cascade='save-update, merge',
        overlaps='attempts,session_item',
        lazy='noload',
    )
    evaluation_runs: Mapped[list[QbEvaluationRun]] = relationship(
        init=False,
        back_populates='session',
        cascade='save-update, merge',
        overlaps='attempt,evaluation_runs',
        lazy='noload',
    )


class QbPracticeSessionItem(Base):
    """Delivered question snapshot that pins the exact revision seen by a user."""

    __tablename__ = 'qbank_v2_practice_session_item'
    __table_args__ = (
        sa.UniqueConstraint('session_id', 'position', 'deleted', name='uq_qbv2_sitem_position'),
        sa.UniqueConstraint('session_id', 'question_id', 'deleted', name='uq_qbv2_sitem_question'),
        sa.UniqueConstraint('session_id', 'id', name='uq_qbv2_sitem_session_id'),
        sa.ForeignKeyConstraint(
            ['question_id'],
            ['qbank_v2_question.id'],
            name='fk_qbv2_sitem_question',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['question_id', 'bank_item_id'],
            ['qbank_v2_bank_item.question_id', 'qbank_v2_bank_item.id'],
            name='fk_qbv2_sitem_bank_item_context',
            ondelete='RESTRICT',
        ),
        sa.CheckConstraint('position >= 0', name='ck_qbv2_sitem_position'),
        sa.CheckConstraint('max_score >= 0', name='ck_qbv2_sitem_max_score'),
        sa.Index('ix_qbv2_sitem_delivery_order', 'session_id', 'position'),
        {'comment': '会话投递题目表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    session_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_practice_session.id', ondelete='CASCADE'),
        comment='练习会话 ID',
    )
    question_id: Mapped[int] = mapped_column(sa.BigInteger, comment='题目身份 ID')
    position: Mapped[int] = mapped_column(sa.Integer, comment='投递顺序，从 0 开始')
    bank_item_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        default=None,
        comment='来源题库编排项 ID',
    )
    max_score: Mapped[Decimal] = mapped_column(sa.Numeric(8, 2), default=Decimal('1.00'), comment='本次作答满分')
    display_config: Mapped[dict[str, Any]] = mapped_column(
        CompatibleJSONB,
        default_factory=dict,
        comment='本次投递的选项顺序等展示快照',
    )

    session: Mapped[QbPracticeSession] = relationship(init=False, back_populates='items', lazy='noload')
    question: Mapped[QbQuestion] = relationship(
        init=False,
        foreign_keys=[question_id],
        lazy='noload',
    )
    response: Mapped[QbPracticeSessionResponse | None] = relationship(
        init=False,
        back_populates='session_item',
        uselist=False,
        cascade='all, delete-orphan',
        lazy='noload',
    )
    attempts: Mapped[list[QbQuestionAttempt]] = relationship(
        init=False,
        back_populates='session_item',
        cascade='save-update, merge',
        overlaps='attempts,session',
        lazy='noload',
    )


class QbPracticeSessionResponse(Base):
    """Mutable autosaved response state; submissions remain append-only attempts."""

    __tablename__ = 'qbank_v2_practice_session_response'
    __table_args__ = (
        sa.UniqueConstraint('session_item_id', name='uq_qbv2_response_item'),
        sa.ForeignKeyConstraint(
            ['session_id', 'session_item_id'],
            ['qbank_v2_practice_session_item.session_id', 'qbank_v2_practice_session_item.id'],
            name='fk_qbv2_response_session_item',
            ondelete='CASCADE',
        ),
        sa.CheckConstraint(
            "status IN ('not_started','viewing','answered','submitted','graded','review_required')",
            name='ck_qbv2_response_status',
        ),
        sa.CheckConstraint(
            "grading_status IN ('not_requested','pending','graded','review_required','failed')",
            name='ck_qbv2_response_grading',
        ),
        sa.CheckConstraint('duration_ms >= 0', name='ck_qbv2_response_duration'),
        sa.CheckConstraint('save_version >= 0', name='ck_qbv2_response_version'),
        sa.CheckConstraint('score IS NULL OR score >= 0', name='ck_qbv2_response_score'),
        sa.Index('ix_qbv2_response_session_status', 'session_id', 'status'),
        sa.Index('ix_qbv2_response_last_saved', 'session_id', 'last_saved_time'),
        {'comment': '会话题目可变草稿与当前判分状态表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    session_id: Mapped[int] = mapped_column(sa.BigInteger, comment='练习会话 ID')
    session_item_id: Mapped[int] = mapped_column(sa.BigInteger, comment='投递题目 ID')
    response_data: Mapped[Any | None] = mapped_column(CompatibleJSONB, default=None, comment='当前未提交或已提交答案')
    status: Mapped[str] = mapped_column(sa.String(24), default='not_started', comment='作答界面状态')
    is_flagged: Mapped[bool] = mapped_column(default=False, comment='答题卡稍后检查标记')
    duration_ms: Mapped[int] = mapped_column(sa.BigInteger, default=0, comment='累计有效作答时长毫秒')
    save_version: Mapped[int] = mapped_column(sa.Integer, default=0, comment='乐观并发保存版本号')
    is_correct: Mapped[bool | None] = mapped_column(default=None, comment='当前提交判定结果')
    score: Mapped[Decimal | None] = mapped_column(sa.Numeric(8, 2), default=None, comment='当前提交得分')
    grading_status: Mapped[str] = mapped_column(
        sa.String(24),
        default='not_requested',
        comment='当前提交判分状态',
    )
    first_viewed_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='首次查看时间')
    last_saved_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近自动保存时间')
    last_submitted_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近提交时间')
    graded_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近判分完成时间')

    session_item: Mapped[QbPracticeSessionItem] = relationship(
        init=False,
        back_populates='response',
        foreign_keys=[session_id, session_item_id],
        lazy='noload',
    )


class QbQuestionAttempt(Base):
    """Append-oriented submission fact used as the source of grading and analytics."""

    __tablename__ = 'qbank_v2_question_attempt'
    __table_args__ = (
        sa.UniqueConstraint('session_item_id', 'attempt_no', 'deleted', name='uq_qbv2_attempt_item_no'),
        sa.UniqueConstraint('user_id', 'id', name='uq_qbv2_attempt_user_id'),
        sa.UniqueConstraint('user_id', 'question_id', 'id', name='uq_qbv2_attempt_user_question_id'),
        sa.ForeignKeyConstraint(
            ['question_id'],
            ['qbank_v2_question.id'],
            name='fk_qbv2_attempt_question',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['user_id', 'session_id'],
            ['qbank_v2_practice_session.user_id', 'qbank_v2_practice_session.id'],
            name='fk_qbv2_attempt_user_session',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['session_id', 'session_item_id'],
            ['qbank_v2_practice_session_item.session_id', 'qbank_v2_practice_session_item.id'],
            name='fk_qbv2_attempt_session_item',
            ondelete='SET NULL',
        ),
        sa.CheckConstraint(
            '(session_id IS NULL AND session_item_id IS NULL) '
            'OR (session_id IS NOT NULL AND session_item_id IS NOT NULL)',
            name='ck_qbv2_attempt_session_item_pair',
        ),
        sa.CheckConstraint('attempt_no > 0', name='ck_qbv2_attempt_no'),
        sa.CheckConstraint('score IS NULL OR score >= 0', name='ck_qbv2_attempt_score'),
        sa.CheckConstraint('duration_ms IS NULL OR duration_ms >= 0', name='ck_qbv2_attempt_duration'),
        sa.CheckConstraint(
            "grading_status IN ('pending','graded','review_required','failed')",
            name='ck_qbv2_attempt_grading_status',
        ),
        sa.CheckConstraint(
            "grading_method IN ('rule','ai','manual','hybrid')",
            name='ck_qbv2_attempt_grading_method',
        ),
        sa.Index('ix_qbv2_attempt_user_question_time', 'user_id', 'question_id', 'submitted_time'),
        sa.Index('ix_qbv2_attempt_session', 'session_id', 'session_item_id'),
        {'comment': '题目作答事实表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='RESTRICT'),
        comment='答题用户 ID',
    )
    question_id: Mapped[int] = mapped_column(sa.BigInteger, comment='题目身份 ID')
    response_data: Mapped[Any] = mapped_column(CompatibleJSONB, comment='用户提交的结构化答案快照')
    content_hash: Mapped[str | None] = mapped_column(
        sa.String(64),
        default=None,
        comment='作答时的题目内容哈希，用于审计',
    )
    session_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        default=None,
        comment='所属会话 ID；独立作答可为空',
    )
    session_item_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        default=None,
        comment='投递题目 ID',
    )
    attempt_no: Mapped[int] = mapped_column(sa.Integer, default=1, comment='同投递题第几次提交')
    is_correct: Mapped[bool | None] = mapped_column(default=None, comment='客观题判定；主观题待批时为空')
    score: Mapped[Decimal | None] = mapped_column(sa.Numeric(8, 2), default=None, comment='本次得分')
    duration_ms: Mapped[int | None] = mapped_column(sa.Integer, default=None, comment='作答耗时毫秒')
    grading_status: Mapped[str] = mapped_column(sa.String(24), default='pending', comment='判分状态')
    grading_method: Mapped[str] = mapped_column(sa.String(16), default='rule', comment='实际判分方式')
    grading_result: Mapped[dict[str, Any]] = mapped_column(
        CompatibleJSONB,
        default_factory=dict,
        comment='规则判分明细；外部评估审计见 evaluation_run',
    )
    submitted_time: Mapped[datetime] = mapped_column(
        TimeZone,
        default_factory=timezone.now,
        comment='提交时间',
    )

    session: Mapped[QbPracticeSession | None] = relationship(
        init=False,
        back_populates='attempts',
        foreign_keys=[user_id, session_id],
        overlaps='attempts,session_item',
        lazy='noload',
    )
    session_item: Mapped[QbPracticeSessionItem | None] = relationship(
        init=False,
        back_populates='attempts',
        foreign_keys=[session_id, session_item_id],
        overlaps='attempts,session',
        lazy='noload',
    )
    question: Mapped[QbQuestion] = relationship(
        init=False,
        foreign_keys=[question_id],
        lazy='noload',
    )
    evaluation_runs: Mapped[list[QbEvaluationRun]] = relationship(
        init=False,
        back_populates='attempt',
        cascade='save-update, merge',
        overlaps='evaluation_runs,session',
        lazy='noload',
    )
    assets: Mapped[list[QbQuestionAttemptAsset]] = relationship(
        init=False,
        back_populates='attempt',
        cascade='save-update, merge',
        lazy='noload',
    )
