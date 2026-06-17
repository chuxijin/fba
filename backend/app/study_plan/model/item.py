#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, UserMixin, id_key

CompatibleJSONB = sa.JSON().with_variant(JSONB, 'postgresql')

if TYPE_CHECKING:
    from .plan import StudyPlan
    from .record import StudyPlanRecord


class StudyPlanItem(Base, UserMixin):
    """学习计划项表"""

    __tablename__ = 'study_plan_item'
    __table_args__ = (
        sa.Index('idx_study_plan_item_plan_date_order', 'plan_id', 'plan_date', 'order_index'),
        sa.Index('idx_study_plan_item_user_date_status', 'user_id', 'plan_date', 'status'),
        sa.Index(
            'idx_study_plan_item_ref',
            'ref_type',
            'ref_id',
            postgresql_where=sa.text('ref_id IS NOT NULL'),
        ),
        sa.CheckConstraint(
            "module_type IN ('review','practice','wrong_review','ability','resource')",
            name='ck_study_plan_item_module_type',
        ),
        sa.CheckConstraint(
            "ref_type IN ('content','question_set','wrong_dynamic','ability_task')",
            name='ck_study_plan_item_ref_type',
        ),
        sa.CheckConstraint(
            "status IN ('pending','in_progress','completed','skipped')",
            name='ck_study_plan_item_status',
        ),
        sa.CheckConstraint('order_index >= 0', name='ck_study_plan_item_order'),
        sa.CheckConstraint('expected_minutes >= 0', name='ck_study_plan_item_minutes'),
        {'comment': '学习计划项表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    plan_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_plan.id', ondelete='CASCADE'),
        comment='所属计划 ID',
    )
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_user_account.user_id', ondelete='CASCADE'),
        comment='学员用户 ID（冗余，加速按学员查询）',
    )
    plan_date: Mapped[date] = mapped_column(sa.Date, comment='所属日期')
    order_index: Mapped[int] = mapped_column(sa.Integer, comment='当日顺序（从 0 开始）')
    module_type: Mapped[str] = mapped_column(
        sa.String(16),
        comment='模块类型: review/practice/wrong_review/ability',
    )
    title: Mapped[str] = mapped_column(sa.String(255), comment='模块标题')
    ref_type: Mapped[str] = mapped_column(
        sa.String(32),
        comment='引用类型: content/question_set/wrong_dynamic/ability_task',
    )
    ref_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        default=None,
        comment='引用目标 ID（软引用；wrong_dynamic 为 null，由服务端动态计算）',
    )
    expected_minutes: Mapped[int] = mapped_column(sa.Integer, default=15, comment='预计耗时（分钟）')
    status: Mapped[str] = mapped_column(
        sa.String(16),
        default='pending',
        comment='状态: pending/in_progress/completed/skipped',
    )
    extra: Mapped[dict | None] = mapped_column(
        CompatibleJSONB,
        default=None,
        comment='模块特定配置（如刷题 required_accuracy/knowledge_points/question_ids、学习 cloud_links）',
    )

    # ============ 关系 ============
    plan: Mapped[StudyPlan] = relationship(init=False, back_populates='items', lazy='noload')
    records: Mapped[list[StudyPlanRecord]] = relationship(
        init=False,
        back_populates='item',
        lazy='noload',
        cascade='all, delete-orphan',
    )
