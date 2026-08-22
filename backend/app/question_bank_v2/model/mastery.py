from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, TimeZone, id_key

if TYPE_CHECKING:
    from .knowledge import QbKnowledgePoint, QbKnowledgeSystem
    from .practice import QbQuestionAttempt


class QbQuestionAttemptKnowledgePoint(Base):
    """Knowledge-point mapping captured at the time of an attempt."""

    __tablename__ = 'qbank_v2_question_attempt_knowledge_point'
    __table_args__ = (
        sa.UniqueConstraint(
            'attempt_id',
            'system_id',
            'knowledge_point_id',
            'deleted',
            name='uq_qbv2_attempt_kp_snapshot',
        ),
        sa.ForeignKeyConstraint(
            ['attempt_id'],
            ['qbank_v2_question_attempt.id'],
            name='fk_qbv2_attempt_kp_snapshot_attempt',
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['system_id'],
            ['qbank_v2_knowledge_system.id'],
            name='fk_qbv2_attempt_kp_snapshot_system',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['knowledge_point_id'],
            ['qbank_v2_knowledge_point.id'],
            name='fk_qbv2_attempt_kp_snapshot_point',
            ondelete='RESTRICT',
        ),
        sa.CheckConstraint("role IN ('primary','secondary','prerequisite')", name='ck_qbv2_attempt_kp_role'),
        sa.CheckConstraint('weight > 0 AND weight <= 1', name='ck_qbv2_attempt_kp_weight'),
        sa.CheckConstraint(
            'correctness IS NULL OR correctness BETWEEN 0 AND 1',
            name='ck_qbv2_attempt_kp_correctness',
        ),
        sa.Index('ix_qbv2_attempt_kp_user_system_point', 'user_id', 'system_id', 'knowledge_point_id'),
        sa.Index('ix_qbv2_attempt_kp_attempt', 'attempt_id', 'system_id'),
        {'comment': '作答发生时的题目知识点关联快照'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    attempt_id: Mapped[int] = mapped_column(sa.BigInteger, comment='作答事实 ID')
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    question_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_question.id', ondelete='RESTRICT'),
        comment='题目 ID',
    )
    system_id: Mapped[int] = mapped_column(sa.BigInteger, comment='知识体系 ID')
    knowledge_point_id: Mapped[int] = mapped_column(sa.BigInteger, comment='知识点 ID')
    weight: Mapped[Decimal] = mapped_column(sa.Numeric(7, 6), comment='题内归一化权重')
    role: Mapped[str] = mapped_column(sa.String(16), default='primary', comment='知识点角色快照')
    source: Mapped[str] = mapped_column(sa.String(16), default='manual', comment='标注来源快照')
    correctness: Mapped[Decimal | None] = mapped_column(
        sa.Numeric(7, 6),
        default=None,
        comment='本题对该知识点的得分率；待判分时为空',
    )
    evidence_applied: Mapped[bool] = mapped_column(default=False, comment='是否已写入掌握度投影')
    graded_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='证据判分时间')

    attempt: Mapped[QbQuestionAttempt] = relationship(init=False, lazy='noload')
    system: Mapped[QbKnowledgeSystem] = relationship(init=False, lazy='noload')
    knowledge_point: Mapped[QbKnowledgePoint] = relationship(init=False, lazy='noload')


class QbUserKnowledgeMastery(Base):
    """Rebuildable per-user, per-system, per-knowledge-point mastery projection."""

    __tablename__ = 'qbank_v2_user_knowledge_mastery'
    __table_args__ = (
        sa.UniqueConstraint(
            'user_id',
            'system_id',
            'knowledge_point_id',
            'deleted',
            name='uq_qbv2_user_system_knowledge_mastery',
        ),
        sa.ForeignKeyConstraint(
            ['system_id'],
            ['qbank_v2_knowledge_system.id'],
            name='fk_qbv2_user_kmastery_system',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['knowledge_point_id'],
            ['qbank_v2_knowledge_point.id'],
            name='fk_qbv2_user_kmastery_point',
            ondelete='RESTRICT',
        ),
        sa.CheckConstraint(
            "state IN ('unknown','learning','stable','mastered')",
            name='ck_qbv2_user_kmastery_state',
        ),
        sa.CheckConstraint('mastery_score BETWEEN 0 AND 1', name='ck_qbv2_user_kmastery_score'),
        sa.CheckConstraint('confidence_score BETWEEN 0 AND 1', name='ck_qbv2_user_kmastery_confidence'),
        sa.CheckConstraint('effective_sample_size >= 0', name='ck_qbv2_user_kmastery_effective_sample'),
        sa.CheckConstraint('attempt_count >= 0 AND correct_count >= 0', name='ck_qbv2_user_kmastery_count'),
        sa.CheckConstraint('correct_count <= attempt_count', name='ck_qbv2_user_kmastery_correct'),
        sa.Index('ix_qbv2_user_kmastery_scope', 'user_id', 'system_id', 'state', 'knowledge_point_id'),
        sa.Index('ix_qbv2_user_kmastery_point', 'knowledge_point_id', 'system_id', 'state'),
        {'comment': '用户知识点掌握度投影'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    system_id: Mapped[int] = mapped_column(sa.BigInteger, comment='知识体系 ID')
    knowledge_point_id: Mapped[int] = mapped_column(sa.BigInteger, comment='知识点 ID')
    mastery_score: Mapped[Decimal] = mapped_column(
        sa.Numeric(7, 6),
        default=Decimal('0.500000'),
        comment='当前掌握度，带时间衰减',
    )
    confidence_score: Mapped[Decimal] = mapped_column(
        sa.Numeric(7, 6),
        default=Decimal('0.000000'),
        comment='掌握度证据可信度',
    )
    effective_sample_size: Mapped[Decimal] = mapped_column(
        sa.Numeric(14, 6),
        default=Decimal('0.000000'),
        comment='衰减后的有效样本量',
    )
    attempt_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='参与掌握度的作答次数')
    correct_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='客观答对次数')
    weighted_correct: Mapped[Decimal] = mapped_column(
        sa.Numeric(14, 6),
        default=Decimal('0.000000'),
        comment='衰减后的正确证据',
    )
    weighted_wrong: Mapped[Decimal] = mapped_column(
        sa.Numeric(14, 6),
        default=Decimal('0.000000'),
        comment='衰减后的错误证据',
    )
    lifetime_correct_weight: Mapped[Decimal] = mapped_column(
        sa.Numeric(14, 6),
        default=Decimal('0.000000'),
        comment='生命周期正确证据',
    )
    lifetime_wrong_weight: Mapped[Decimal] = mapped_column(
        sa.Numeric(14, 6),
        default=Decimal('0.000000'),
        comment='生命周期错误证据',
    )
    last_attempt_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近证据时间')
    state: Mapped[str] = mapped_column(sa.String(16), default='unknown', comment='unknown/learning/stable/mastered')
    model_version: Mapped[str] = mapped_column(sa.String(32), default='beta_decay_v1', comment='掌握度模型版本')
    calculated_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近计算时间')
