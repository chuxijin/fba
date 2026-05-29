#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, TimeZone, id_key
from backend.utils.timezone import timezone

if TYPE_CHECKING:
    from .bank import QuestionBank
    from .question import Question, QuestionPlacement
    from .user import UserAccount


class UserBankQuestionProgress(Base):
    """用户内容题目进度汇总表"""

    __tablename__ = 'study_user_bank_question_progress'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'bank_id', 'question_id', name='uq_user_bank_question_progress'),
        sa.Index('idx_user_bank_progress_user_bank', 'user_id', 'bank_id'),
        sa.Index('idx_user_bank_progress_user_bank_correct', 'user_id', 'bank_id', 'is_correct'),
        sa.Index('idx_user_bank_progress_question', 'question_id'),
        {'comment': '用户内容题目进度汇总表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_user_account.user_id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    bank_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question_bank.id', ondelete='CASCADE'),
        comment='内容 ID',
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
        comment='最近一次作答挂载 ID',
    )
    is_correct: Mapped[bool] = mapped_column(default=False, comment='是否曾经答对')
    first_answered_time: Mapped[datetime] = mapped_column(
        TimeZone,
        default_factory=timezone.now,
        comment='首次作答时间',
    )
    last_answered_time: Mapped[datetime] = mapped_column(
        TimeZone,
        default_factory=timezone.now,
        comment='最近作答时间',
    )
    last_correct_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近答对时间')

    account: Mapped['UserAccount'] = relationship(init=False, lazy='noload')
    bank: Mapped['QuestionBank'] = relationship(init=False, lazy='noload')
    question: Mapped['Question'] = relationship(init=False, lazy='noload')
    placement: Mapped['QuestionPlacement | None'] = relationship(init=False, lazy='noload')
