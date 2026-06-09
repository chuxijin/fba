#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, UserMixin, id_key

CompatibleJSONB = sa.JSON().with_variant(JSONB, 'postgresql')

if TYPE_CHECKING:
    pass


class StudyPlanTemplate(Base, UserMixin):
    """学习计划模板表"""

    __tablename__ = 'study_plan_template'
    __table_args__ = (
        sa.Index('idx_study_plan_template_domain_active', 'domain', 'is_active'),
        sa.Index('idx_study_plan_template_creator', 'created_by'),
        sa.CheckConstraint('duration_days > 0', name='ck_study_plan_template_duration'),
        {'comment': '学习计划模板表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(sa.String(255), comment='模板名称')
    duration_days: Mapped[int] = mapped_column(sa.Integer, comment='覆盖天数')
    domain: Mapped[str] = mapped_column(
        sa.String(32), default='civil_service', comment='业务领域: civil_service',
    )
    description: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='模板说明')
    is_active: Mapped[bool] = mapped_column(default=True, comment='是否启用')

    # ============ 关系 ============
    items: Mapped[list[StudyPlanTemplateItem]] = relationship(
        init=False,
        back_populates='template',
        lazy='noload',
        cascade='all, delete-orphan',
    )


class StudyPlanTemplateItem(Base):
    """学习计划模板项表"""

    __tablename__ = 'study_plan_template_item'
    __table_args__ = (
        sa.UniqueConstraint(
            'template_id', 'day_index', 'order_index',
            name='uq_study_plan_template_item_position',
        ),
        sa.Index(
            'idx_study_plan_template_item_template_day',
            'template_id', 'day_index', 'order_index',
        ),
        sa.CheckConstraint(
            "module_type IN ('review','practice','wrong_review','ability')",
            name='ck_study_plan_template_item_module_type',
        ),
        sa.CheckConstraint(
            "ref_type IN ('content','question_set','wrong_dynamic','ability_task')",
            name='ck_study_plan_template_item_ref_type',
        ),
        sa.CheckConstraint('day_index > 0', name='ck_study_plan_template_item_day'),
        sa.CheckConstraint('order_index >= 0', name='ck_study_plan_template_item_order'),
        sa.CheckConstraint('expected_minutes >= 0', name='ck_study_plan_template_item_minutes'),
        {'comment': '学习计划模板项表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    template_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_plan_template.id', ondelete='CASCADE'),
        comment='所属模板 ID',
    )
    day_index: Mapped[int] = mapped_column(sa.Integer, comment='第几天（1..duration_days）')
    order_index: Mapped[int] = mapped_column(sa.Integer, comment='当天顺序（从 0 开始）')
    module_type: Mapped[str] = mapped_column(
        sa.String(16), comment='模块类型: review/practice/wrong_review/ability',
    )
    title: Mapped[str] = mapped_column(sa.String(255), comment='模块标题')
    ref_type: Mapped[str] = mapped_column(
        sa.String(32), comment='引用类型: content/question_set/wrong_dynamic/ability_task',
    )
    ref_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, default=None, comment='引用目标 ID（软引用）',
    )
    expected_minutes: Mapped[int] = mapped_column(sa.Integer, default=15, comment='预计耗时（分钟）')
    extra: Mapped[dict | None] = mapped_column(
        CompatibleJSONB, default=None, comment='模块特定配置（同 study_plan_item.extra）',
    )

    # ============ 关系 ============
    template: Mapped[StudyPlanTemplate] = relationship(
        init=False, back_populates='items', lazy='noload',
    )
