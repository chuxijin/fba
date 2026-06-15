#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, TimeZone, UserMixin, id_key
from backend.utils.timezone import timezone

if TYPE_CHECKING:
    from .practice import WrongQuestionBook, WrongQuestionCustom
    from .question import Question


class WrongMasteryStatus(Base, UserMixin):
    """错题掌握状态表"""

    __tablename__ = 'study_mastery_status'
    __table_args__ = (
        sa.Index('idx_mastery_user_status', 'user_id', 'status'),
        sa.Index('idx_mastery_user_question', 'user_id', 'question_id'),
        sa.Index('idx_mastery_next_review', 'user_id', 'next_review_time'),
        sa.CheckConstraint("status IN ('learning', 'mastered', 'forgotten')", name='ck_mastery_status'),
        sa.CheckConstraint(
            "(question_id IS NOT NULL AND custom_question_id IS NULL) OR "
            "(question_id IS NULL AND custom_question_id IS NOT NULL)",
            name='ck_mastery_source',
        ),
        {'comment': '错题掌握状态表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_user_account.user_id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    question_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question.id', ondelete='CASCADE'),
        default=None,
        comment='关联题库题目 ID',
    )
    custom_question_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_wrong_question_custom.id', ondelete='CASCADE'),
        default=None,
        comment='关联自定义错题 ID',
    )
    status: Mapped[str] = mapped_column(
        sa.String(16),
        default='learning',
        comment='状态: learning/mastered/forgotten',
    )
    correct_streak: Mapped[int] = mapped_column(
        sa.Integer,
        default=0,
        comment='连续答对次数',
    )
    review_count: Mapped[int] = mapped_column(
        sa.Integer,
        default=0,
        comment='复盘次数',
    )
    last_practice_time: Mapped[datetime | None] = mapped_column(
        TimeZone,
        default=None,
        comment='最后一次练习时间',
    )
    last_review_time: Mapped[datetime | None] = mapped_column(
        TimeZone,
        default=None,
        comment='最后一次复盘时间',
    )
    mastered_time: Mapped[datetime | None] = mapped_column(
        TimeZone,
        default=None,
        comment='首次掌握时间',
    )
    next_review_time: Mapped[datetime | None] = mapped_column(
        TimeZone,
        default=None,
        comment='下次建议复习时间',
    )

    # ============ 关系 ============
    question: Mapped[Question | None] = relationship(init=False, lazy='noload')
    custom_question: Mapped[WrongQuestionCustom | None] = relationship(init=False, lazy='noload')
