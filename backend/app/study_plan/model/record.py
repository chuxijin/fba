#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, TimeZone, id_key
from backend.utils.timezone import timezone

CompatibleJSONB = sa.JSON().with_variant(JSONB, 'postgresql')

if TYPE_CHECKING:
    from .item import StudyPlanItem


class StudyPlanRecord(Base):
    """学习计划完成记录表"""

    __tablename__ = 'study_plan_record'
    __table_args__ = (
        sa.Index('idx_study_plan_record_user_time', 'user_id', 'completed_at'),
        sa.Index('idx_study_plan_record_item', 'item_id'),
        sa.CheckConstraint('duration_seconds >= 0', name='ck_study_plan_record_duration'),
        sa.CheckConstraint(
            '(correct_count IS NULL OR correct_count >= 0)'
            ' AND (total_count IS NULL OR total_count >= 0)'
            ' AND (correct_count IS NULL OR total_count IS NULL OR correct_count <= total_count)',
            name='ck_study_plan_record_counts',
        ),
        sa.CheckConstraint('score IS NULL OR score >= 0', name='ck_study_plan_record_score'),
        {'comment': '学习计划完成记录表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    item_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_plan_item.id', ondelete='CASCADE'),
        comment='所属计划项 ID',
    )
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_user_account.user_id', ondelete='CASCADE'),
        comment='学员用户 ID',
    )
    duration_seconds: Mapped[int] = mapped_column(sa.Integer, default=0, comment='实际耗时（秒）')
    score: Mapped[int | None] = mapped_column(sa.Integer, default=None, comment='得分（刷题类）')
    correct_count: Mapped[int | None] = mapped_column(sa.Integer, default=None, comment='正确题数（刷题类）')
    total_count: Mapped[int | None] = mapped_column(sa.Integer, default=None, comment='总题数（刷题类）')
    extra_data: Mapped[dict | None] = mapped_column(
        CompatibleJSONB,
        default=None,
        comment='扩展数据（如错题复盘对应的 WrongQuestionReview ID 列表）',
    )
    completed_at: Mapped[datetime] = mapped_column(
        TimeZone, default_factory=timezone.now, comment='完成时间',
    )

    # ============ 关系 ============
    item: Mapped[StudyPlanItem] = relationship(init=False, back_populates='records', lazy='noload')
