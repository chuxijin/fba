#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, TimeZone, UniversalText, UserMixin, id_key

CompatibleJSONB = sa.JSON().with_variant(JSONB, 'postgresql')

if TYPE_CHECKING:
    from .practice import PracticeSession, SessionQuestion
    from .question import Question
    from .user import UserAccount


class PracticeAIEvaluation(Base, UserMixin):
    """练习 AI 评估结果表"""

    __tablename__ = 'study_practice_ai_evaluation'
    __table_args__ = (
        sa.Index('idx_practice_ai_eval_user_target_created', 'user_id', 'target_type', 'created_time'),
        sa.Index('idx_practice_ai_eval_session_latest', 'session_id', 'target_type', 'is_latest'),
        sa.Index('idx_practice_ai_eval_sq_latest', 'session_question_id', 'is_latest'),
        sa.Index('idx_practice_ai_eval_question_created', 'question_id', 'created_time'),
        sa.CheckConstraint(
            "target_type IN ('question_eval','session_summary')",
            name='ck_practice_ai_eval_target_type',
        ),
        sa.CheckConstraint(
            "trigger_source IN ('auto','manual')",
            name='ck_practice_ai_eval_trigger_source',
        ),
        sa.CheckConstraint(
            "status IN ('pending','succeeded','failed')",
            name='ck_practice_ai_eval_status',
        ),
        sa.CheckConstraint(
            '(score IS NULL OR score >= 0) AND (max_score IS NULL OR max_score >= 0)',
            name='ck_practice_ai_eval_score',
        ),
        sa.CheckConstraint(
            '(confidence IS NULL OR (confidence >= 0 AND confidence <= 1))',
            name='ck_practice_ai_eval_confidence',
        ),
        {'comment': '练习 AI 评估结果表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_user_account.user_id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    target_type: Mapped[str] = mapped_column(sa.String(32), comment='目标类型')
    session_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_practice_session.id', ondelete='CASCADE'),
        default=None,
        comment='练习会话 ID',
    )
    session_question_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_session_question.id', ondelete='CASCADE'),
        default=None,
        comment='会话题目 ID（答题记录）',
    )
    question_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question.id', ondelete='SET NULL'),
        default=None,
        comment='题目 ID',
    )
    trigger_source: Mapped[str] = mapped_column(
        sa.String(16),
        default='auto',
        comment='触发来源: auto/manual',
    )
    status: Mapped[str] = mapped_column(sa.String(16), default='pending', comment='状态')
    provider_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='AI 供应商 ID')
    model_name: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='模型名称')
    prompt_version: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='提示词版本')
    score: Mapped[Decimal | None] = mapped_column(sa.Numeric(8, 2), default=None, comment='得分')
    max_score: Mapped[Decimal | None] = mapped_column(sa.Numeric(8, 2), default=None, comment='满分')
    confidence: Mapped[Decimal | None] = mapped_column(sa.Numeric(5, 4), default=None, comment='置信度')
    summary_text: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='摘要文本')
    request_payload: Mapped[dict | None] = mapped_column(CompatibleJSONB, default=None, comment='请求快照')
    result_payload: Mapped[dict | None] = mapped_column(CompatibleJSONB, default=None, comment='结果快照')
    error_message: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='错误信息')
    started_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='开始时间')
    finished_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='结束时间')
    is_latest: Mapped[bool] = mapped_column(default=True, comment='是否最新结果')

    account: Mapped[UserAccount] = relationship(init=False, lazy='noload')
    session: Mapped[PracticeSession | None] = relationship(init=False, lazy='noload')
    session_question: Mapped[SessionQuestion | None] = relationship(init=False, lazy='noload')
    question: Mapped[Question | None] = relationship(init=False, lazy='noload')
