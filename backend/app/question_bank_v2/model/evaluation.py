from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, TimeZone, UniversalText, id_key

from .common import CompatibleJSONB

if TYPE_CHECKING:
    from .practice import QbPracticeSession, QbQuestionAttempt


class QbEvaluationRun(Base):
    """Auditable grading or feedback execution, independent from any AI vendor."""

    __tablename__ = 'qbank_v2_evaluation_run'
    __table_args__ = (
        sa.ForeignKeyConstraint(
            ['user_id', 'session_id'],
            ['qbank_v2_practice_session.user_id', 'qbank_v2_practice_session.id'],
            name='fk_qbv2_eval_user_session',
            ondelete='RESTRICT',
        ),
        sa.ForeignKeyConstraint(
            ['user_id', 'attempt_id'],
            ['qbank_v2_question_attempt.user_id', 'qbank_v2_question_attempt.id'],
            name='fk_qbv2_eval_user_attempt',
            ondelete='RESTRICT',
        ),
        sa.CheckConstraint(
            "purpose IN ('attempt_grading','attempt_feedback','session_summary')",
            name='ck_qbv2_eval_purpose',
        ),
        sa.CheckConstraint(
            "engine_type IN ('rule','ai','agent','manual')",
            name='ck_qbv2_eval_engine',
        ),
        sa.CheckConstraint(
            "trigger_source IN ('auto','manual','retry')",
            name='ck_qbv2_eval_trigger',
        ),
        sa.CheckConstraint(
            "status IN ('queued','running','succeeded','failed','cancelled')",
            name='ck_qbv2_eval_status',
        ),
        sa.CheckConstraint(
            "(purpose IN ('attempt_grading','attempt_feedback') AND attempt_id IS NOT NULL AND session_id IS NULL) "
            "OR (purpose = 'session_summary' AND session_id IS NOT NULL AND attempt_id IS NULL)",
            name='ck_qbv2_eval_target',
        ),
        sa.CheckConstraint(
            '(score IS NULL OR score >= 0) AND (max_score IS NULL OR max_score >= 0)',
            name='ck_qbv2_eval_score',
        ),
        sa.CheckConstraint(
            'confidence IS NULL OR confidence BETWEEN 0 AND 1',
            name='ck_qbv2_eval_confidence',
        ),
        sa.Index('ix_qbv2_eval_attempt_created', 'attempt_id', 'purpose', 'created_time'),
        sa.Index('ix_qbv2_eval_session_created', 'session_id', 'purpose', 'created_time'),
        sa.Index('ix_qbv2_eval_user_status', 'user_id', 'status', 'created_time'),
        sa.Index('ix_qbv2_eval_supersedes', 'supersedes_id'),
        sa.Index(
            'uq_qbv2_eval_attempt_latest',
            'attempt_id',
            'purpose',
            unique=True,
            postgresql_where=sa.text('attempt_id IS NOT NULL AND is_latest AND deleted = 0'),
        ).ddl_if(dialect='postgresql'),
        sa.Index(
            'uq_qbv2_eval_session_latest',
            'session_id',
            'purpose',
            unique=True,
            postgresql_where=sa.text('session_id IS NOT NULL AND attempt_id IS NULL AND is_latest AND deleted = 0'),
        ).ddl_if(dialect='postgresql'),
        {'comment': '判分与学习反馈执行审计表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='RESTRICT'),
        comment='结果所属用户 ID',
    )
    purpose: Mapped[str] = mapped_column(sa.String(24), comment='执行目的')
    engine_type: Mapped[str] = mapped_column(sa.String(16), comment='rule/ai/agent/manual')
    session_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        default=None,
        comment='会话 ID',
    )
    attempt_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        default=None,
        comment='作答事实 ID',
    )
    supersedes_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_evaluation_run.id', ondelete='SET NULL'),
        default=None,
        comment='本次结果替代的执行 ID',
    )
    trigger_source: Mapped[str] = mapped_column(sa.String(16), default='auto', comment='auto/manual/retry')
    status: Mapped[str] = mapped_column(sa.String(16), default='queued', comment='执行状态')
    provider: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='模型或人工服务提供方')
    model_name: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='模型完整名称')
    model_version: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='模型固定版本')
    prompt_version: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='提示词版本')
    rubric_version: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='评分量规版本')
    score: Mapped[Decimal | None] = mapped_column(sa.Numeric(8, 2), default=None, comment='得分')
    max_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(8, 2), default=None, comment='满分')
    confidence: Mapped[Decimal | None] = mapped_column(sa.Numeric(5, 4), default=None, comment='置信度')
    needs_manual_review: Mapped[bool] = mapped_column(default=False, comment='是否需要人工复核')
    summary_text: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='面向用户的摘要')
    request_payload: Mapped[dict[str, Any]] = mapped_column(
        CompatibleJSONB,
        default_factory=dict,
        comment='输入、提示词和量规快照',
    )
    result_payload: Mapped[dict[str, Any]] = mapped_column(
        CompatibleJSONB,
        default_factory=dict,
        comment='结构化评分或总结结果',
    )
    error_code: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='失败错误码')
    error_message: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='失败信息')
    started_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='开始时间')
    finished_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='完成时间')
    is_latest: Mapped[bool] = mapped_column(default=True, comment='是否目标的当前结果')

    session: Mapped[QbPracticeSession | None] = relationship(
        init=False,
        back_populates='evaluation_runs',
        foreign_keys=[user_id, session_id],
        overlaps='attempt,evaluation_runs',
        lazy='noload',
    )
    attempt: Mapped[QbQuestionAttempt | None] = relationship(
        init=False,
        back_populates='evaluation_runs',
        foreign_keys=[user_id, attempt_id],
        overlaps='evaluation_runs,session',
        lazy='noload',
    )
    supersedes: Mapped[QbEvaluationRun | None] = relationship(
        init=False,
        remote_side=lambda: [QbEvaluationRun.id],
        lazy='noload',
    )
