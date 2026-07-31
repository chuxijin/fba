from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, TimeZone, id_key

from .common import CompatibleJSONB

if TYPE_CHECKING:
    from .bank import QbBankItem
    from .practice import QbQuestionAttempt


class QbQuestionStatistics(Base):
    """Rebuildable aggregate derived from immutable attempt facts."""

    __tablename__ = 'qbank_v2_question_statistics'
    __table_args__ = (
        sa.UniqueConstraint('question_id', name='uq_qbv2_qstats_question'),
        sa.CheckConstraint('attempt_count >= 0', name='ck_qbv2_qstats_attempt'),
        sa.CheckConstraint(
            'graded_count >= 0 AND graded_count <= attempt_count',
            name='ck_qbv2_qstats_graded',
        ),
        sa.CheckConstraint(
            'correct_count >= 0 AND correct_count <= graded_count',
            name='ck_qbv2_qstats_correct',
        ),
        sa.CheckConstraint('correct_rate BETWEEN 0 AND 1', name='ck_qbv2_qstats_rate'),
        sa.CheckConstraint(
            'avg_score_rate IS NULL OR avg_score_rate BETWEEN 0 AND 1',
            name='ck_qbv2_qstats_score_rate',
        ),
        sa.CheckConstraint('avg_duration_ms IS NULL OR avg_duration_ms >= 0', name='ck_qbv2_qstats_duration'),
        sa.Index('ix_qbv2_qstats_rate_volume', 'correct_rate', 'graded_count'),
        {'comment': '题目派生统计表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    question_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_question.id', ondelete='CASCADE'),
        comment='题目 ID',
    )
    attempt_count: Mapped[int] = mapped_column(sa.BigInteger, default=0, comment='提交次数')
    graded_count: Mapped[int] = mapped_column(sa.BigInteger, default=0, comment='已判分次数')
    correct_count: Mapped[int] = mapped_column(sa.BigInteger, default=0, comment='答对次数')
    correct_rate: Mapped[Decimal] = mapped_column(
        sa.Numeric(7, 6),
        default=Decimal('0.000000'),
        comment='正确率，范围 0-1',
    )
    avg_score_rate: Mapped[Decimal | None] = mapped_column(
        sa.Numeric(7, 6),
        default=None,
        comment='平均得分率，范围 0-1',
    )
    avg_duration_ms: Mapped[Decimal | None] = mapped_column(
        sa.Numeric(14, 2),
        default=None,
        comment='平均作答耗时毫秒',
    )
    response_distribution: Mapped[dict[str, Any]] = mapped_column(
        CompatibleJSONB,
        default_factory=dict,
        comment='选项、填空等回答分布派生统计',
    )
    calculated_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近聚合时间')


class QbUserQuestionMastery(Base):
    """Rebuildable per-user mastery projection; scheduling lives on the wrong-book state."""

    __tablename__ = 'qbank_v2_user_question_mastery'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'question_id', 'deleted', name='uq_qbv2_mastery_user_question'),
        sa.CheckConstraint(
            "state IN ('new','learning','review','mastered','suspended')",
            name='ck_qbv2_mastery_state',
        ),
        sa.CheckConstraint('mastery_score BETWEEN 0 AND 1', name='ck_qbv2_mastery_score'),
        sa.CheckConstraint('attempt_count >= 0 AND correct_count >= 0', name='ck_qbv2_mastery_count'),
        sa.CheckConstraint('correct_count <= attempt_count', name='ck_qbv2_mastery_correct'),
        sa.Index('ix_qbv2_mastery_state', 'user_id', 'state', 'id'),
        sa.Index('ix_qbv2_mastery_question', 'question_id', 'state'),
        {'comment': '用户题目掌握状态表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    question_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_question.id', ondelete='RESTRICT'),
        comment='题目身份 ID',
    )
    state: Mapped[str] = mapped_column(sa.String(16), default='new', comment='学习状态')
    mastery_score: Mapped[Decimal] = mapped_column(
        sa.Numeric(5, 4),
        default=Decimal('0.0000'),
        comment='掌握度，范围 0-1',
    )
    attempt_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='累计提交次数')
    correct_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='累计答对次数')
    last_attempt_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近作答时间')


class QbUserBankItemProgress(Base):
    """Rebuildable per-user progress projection for fast bank and section views."""

    __tablename__ = 'qbank_v2_user_bank_item_progress'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'bank_item_id', 'deleted', name='uq_qbv2_ubip_user_item'),
        sa.ForeignKeyConstraint(
            ['bank_revision_id', 'question_id', 'bank_item_id'],
            [
                'qbank_v2_bank_item.bank_revision_id',
                'qbank_v2_bank_item.question_id',
                'qbank_v2_bank_item.id',
            ],
            name='fk_qbv2_ubip_bank_item',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['user_id', 'question_id', 'last_attempt_id'],
            [
                'qbank_v2_question_attempt.user_id',
                'qbank_v2_question_attempt.question_id',
                'qbank_v2_question_attempt.id',
            ],
            name='fk_qbv2_ubip_last_attempt',
            ondelete='RESTRICT',
        ),
        sa.CheckConstraint(
            'attempt_count > 0 AND correct_count >= 0 AND correct_count <= attempt_count',
            name='ck_qbv2_ubip_counts',
        ),
        sa.CheckConstraint('best_score IS NULL OR best_score >= 0', name='ck_qbv2_ubip_best_score'),
        sa.Index(
            'ix_qbv2_ubip_bank_progress',
            'user_id',
            'bank_revision_id',
            'deleted',
            'last_is_correct',
            'bank_item_id',
        ),
        sa.Index('ix_qbv2_ubip_question', 'user_id', 'question_id', 'last_answered_time'),
        {'comment': '用户题库题项进度投影表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    bank_revision_id: Mapped[int] = mapped_column(sa.BigInteger, comment='题库版本 ID')
    bank_item_id: Mapped[int] = mapped_column(sa.BigInteger, comment='题库版本题项 ID')
    question_id: Mapped[int] = mapped_column(sa.BigInteger, comment='稳定题目 ID')
    attempt_count: Mapped[int] = mapped_column(sa.Integer, default=1, comment='在此题项上的提交次数')
    correct_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='答对次数')
    last_is_correct: Mapped[bool | None] = mapped_column(default=None, comment='最近一次判定结果')
    best_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(8, 2), default=None, comment='历史最高得分')
    last_attempt_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='最近一次作答事实 ID')
    first_answered_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='首次作答时间')
    last_answered_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近作答时间')

    bank_item: Mapped[QbBankItem] = relationship(
        init=False,
        foreign_keys=[bank_revision_id, question_id, bank_item_id],
        lazy='noload',
    )
    last_attempt: Mapped[QbQuestionAttempt | None] = relationship(
        init=False,
        foreign_keys=[user_id, question_id, last_attempt_id],
        overlaps='bank_item',
        lazy='noload',
    )


class QbUserPracticeStatistics(Base):
    """Rebuildable lifetime user statistics used by home pages and rankings."""

    __tablename__ = 'qbank_v2_user_practice_statistics'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'deleted', name='uq_qbv2_user_stats_user'),
        sa.CheckConstraint(
            'session_count >= 0 AND attempt_count >= 0 AND graded_count >= 0 '
            'AND correct_count >= 0 AND graded_count <= attempt_count AND correct_count <= graded_count',
            name='ck_qbv2_user_stats_counts',
        ),
        sa.CheckConstraint(
            'total_duration_ms >= 0 AND practice_days >= 0 AND streak_days >= 0',
            name='ck_qbv2_user_stats_activity',
        ),
        sa.Index('ix_qbv2_user_stats_graded', 'deleted', 'graded_count'),
        sa.Index('ix_qbv2_user_stats_streak', 'deleted', 'streak_days'),
        {'comment': '用户刷题累计统计投影表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    session_count: Mapped[int] = mapped_column(sa.BigInteger, default=0, comment='累计有效会话数')
    attempt_count: Mapped[int] = mapped_column(sa.BigInteger, default=0, comment='累计提交次数')
    graded_count: Mapped[int] = mapped_column(sa.BigInteger, default=0, comment='累计已判分次数')
    correct_count: Mapped[int] = mapped_column(sa.BigInteger, default=0, comment='累计答对次数')
    total_duration_ms: Mapped[int] = mapped_column(sa.BigInteger, default=0, comment='累计有效作答时长毫秒')
    practice_days: Mapped[int] = mapped_column(sa.Integer, default=0, comment='累计练习天数')
    streak_days: Mapped[int] = mapped_column(sa.Integer, default=0, comment='当前连续练习天数')
    last_practice_date: Mapped[date | None] = mapped_column(sa.Date, default=None, comment='最近练习日期')
    calculated_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近聚合时间')


class QbUserDailyStatistics(Base):
    """Rebuildable daily activity aggregate for calendars, trends, and daily ranks."""

    __tablename__ = 'qbank_v2_user_daily_statistics'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'activity_date', 'deleted', name='uq_qbv2_user_daily_date'),
        sa.CheckConstraint(
            'session_count >= 0 AND attempt_count >= 0 AND graded_count >= 0 '
            'AND correct_count >= 0 AND graded_count <= attempt_count AND correct_count <= graded_count',
            name='ck_qbv2_user_daily_counts',
        ),
        sa.CheckConstraint('duration_ms >= 0', name='ck_qbv2_user_daily_duration'),
        sa.Index('ix_qbv2_user_daily_rank', 'activity_date', 'deleted', 'graded_count', 'user_id'),
        {'comment': '用户刷题每日统计投影表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    activity_date: Mapped[date] = mapped_column(sa.Date, comment='业务时区练习日期')
    session_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='当日有效会话数')
    attempt_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='当日提交次数')
    graded_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='当日已判分次数')
    correct_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='当日答对次数')
    duration_ms: Mapped[int] = mapped_column(sa.BigInteger, default=0, comment='当日有效作答时长毫秒')
    first_practice_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='当日首次练习时间')
    last_practice_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='当日最近练习时间')
    calculated_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近聚合时间')
