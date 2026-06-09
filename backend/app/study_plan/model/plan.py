#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, UserMixin, id_key

if TYPE_CHECKING:
    from .item import StudyPlanItem


class StudyPlan(Base, UserMixin):
    """学习计划表"""

    __tablename__ = 'study_plan'
    __table_args__ = (
        sa.Index('idx_study_plan_user_status', 'user_id', 'status'),
        sa.Index('idx_study_plan_user_dates', 'user_id', 'start_date', 'end_date'),
        sa.Index(
            'idx_study_plan_template',
            'template_id',
            postgresql_where=sa.text('template_id IS NOT NULL'),
        ),
        sa.CheckConstraint("status IN ('active','paused','finished')", name='ck_study_plan_status'),
        sa.CheckConstraint('end_date >= start_date', name='ck_study_plan_dates'),
        {'comment': '学习计划表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_user_account.user_id', ondelete='CASCADE'),
        comment='学员用户 ID',
    )
    title: Mapped[str] = mapped_column(sa.String(255), comment='计划标题')
    start_date: Mapped[date] = mapped_column(sa.Date, comment='起始日期')
    end_date: Mapped[date] = mapped_column(sa.Date, comment='结束日期')
    domain: Mapped[str] = mapped_column(
        sa.String(32), default='civil_service', comment='业务领域: civil_service',
    )
    status: Mapped[str] = mapped_column(
        sa.String(16), default='active', comment='状态: active/paused/finished',
    )
    template_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        default=None,
        comment='来源模板 ID（软引用 study_plan_template，T1.3 后补外键）',
    )

    # ============ 关系 ============
    items: Mapped[list[StudyPlanItem]] = relationship(
        init=False,
        back_populates='plan',
        lazy='noload',
        cascade='all, delete-orphan',
    )
