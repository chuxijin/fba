#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, TimeZone, UserMixin, id_key
from backend.utils.timezone import timezone

CompatibleJSONB = sa.JSON().with_variant(JSONB, 'postgresql')

if TYPE_CHECKING:
    from backend.app.admin.model.category import Category
    from backend.app.study_plan.model.item import StudyPlanItem
    from backend.app.study_plan.model.record import StudyPlanRecord


class StudyAbilityCatalog(Base, UserMixin):
    """能力练习目录表"""

    __tablename__ = 'study_ability_catalog'
    __table_args__ = (
        sa.UniqueConstraint('domain', 'ability_key', name='uq_study_ability_catalog_domain_key'),
        sa.Index('idx_study_ability_catalog_domain_active', 'domain', 'is_active'),
        sa.CheckConstraint('default_minutes >= 0', name='ck_study_ability_catalog_minutes'),
        sa.CheckConstraint(
            'default_question_count IS NULL OR default_question_count > 0',
            name='ck_study_ability_catalog_question_count',
        ),
        sa.CheckConstraint(
            'default_accuracy IS NULL OR (default_accuracy >= 0 AND default_accuracy <= 1)',
            name='ck_study_ability_catalog_accuracy',
        ),
        sa.CheckConstraint(
            'benchmark_seconds IS NULL OR benchmark_seconds > 0', name='ck_study_ability_catalog_benchmark'
        ),
        {'comment': '能力练习目录表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    ability_key: Mapped[str] = mapped_column(sa.String(64), comment='能力标识')
    title: Mapped[str] = mapped_column(sa.String(128), comment='能力名称')
    category: Mapped[str] = mapped_column(sa.String(64), comment='能力分类')
    url: Mapped[str] = mapped_column(sa.String(512), comment='小程序入口 URL')
    domain: Mapped[str] = mapped_column(sa.String(32), default='civil_service', comment='业务领域')
    description: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='能力说明')
    default_minutes: Mapped[int] = mapped_column(sa.Integer, default=0, comment='默认预计分钟')
    default_question_count: Mapped[int | None] = mapped_column(sa.Integer, default=None, comment='默认题数')
    default_accuracy: Mapped[Decimal | None] = mapped_column(sa.Numeric(5, 4), default=None, comment='默认正确率')
    benchmark_seconds: Mapped[Decimal | None] = mapped_column(sa.Numeric(8, 2), default=None, comment='速度基准秒')
    supports_study_plan: Mapped[bool] = mapped_column(default=True, comment='是否支持学习计划')
    supports_result: Mapped[bool] = mapped_column(default=True, comment='是否支持自动结算')
    is_active: Mapped[bool] = mapped_column(default=True, comment='是否启用')
    extra: Mapped[dict[str, Any] | None] = mapped_column(CompatibleJSONB, default=None, comment='扩展配置')
    url_base: Mapped[str | None] = mapped_column(
        sa.String(512), default=None, comment='URL 基座（不含 query），与 param_schema 配合派生最终 URL'
    )
    param_schema: Mapped[dict[str, Any] | None] = mapped_column(
        CompatibleJSONB,
        default=None,
        comment='URL 参数 schema，结构: {param_name: {type, label, default, options?, min?, max?, bind_to?}}',
    )


class StudyAbilityCategoryBinding(Base, UserMixin):
    """能力练习分类绑定表"""

    __tablename__ = 'study_ability_category_binding'
    __table_args__ = (
        sa.UniqueConstraint(
            'ability_key',
            'mode',
            'category_id',
            'role',
            name='uq_study_ability_binding_key_mode_category_role',
        ),
        sa.Index('idx_study_ability_binding_key_mode', 'ability_key', 'mode'),
        sa.Index('idx_study_ability_binding_category', 'category_id'),
        sa.CheckConstraint(
            "role IN ('knowledge_point','solution_method','ability')", name='ck_study_ability_binding_role'
        ),
        sa.CheckConstraint('weight > 0', name='ck_study_ability_binding_weight'),
        sa.CheckConstraint('confidence >= 0 AND confidence <= 1', name='ck_study_ability_binding_confidence'),
        {'comment': '能力练习分类绑定表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    ability_key: Mapped[str] = mapped_column(sa.String(64), comment='能力标识')
    category_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_category.id', ondelete='RESTRICT'),
        comment='分类 ID',
    )
    mode: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='练习模式')
    role: Mapped[str] = mapped_column(sa.String(32), default='ability', comment='绑定角色')
    weight: Mapped[Decimal] = mapped_column(sa.Numeric(6, 4), default=Decimal('1'), comment='权重')
    is_primary: Mapped[bool] = mapped_column(default=False, comment='是否主分类')
    source: Mapped[str] = mapped_column(sa.String(32), default='manual', comment='来源')
    confidence: Mapped[Decimal] = mapped_column(sa.Numeric(6, 4), default=Decimal('1'), comment='置信度')

    category: Mapped[Category] = relationship(init=False, lazy='noload')


class StudyAbilityAttempt(Base):
    """能力练习原始记录表"""

    __tablename__ = 'study_ability_attempt'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'client_session_id', name='uq_study_ability_attempt_user_session'),
        sa.Index('idx_study_ability_attempt_user_time', 'user_id', 'completed_at'),
        sa.Index('idx_study_ability_attempt_key_time', 'ability_key', 'completed_at'),
        sa.Index('idx_study_ability_attempt_plan_item', 'study_plan_item_id'),
        sa.CheckConstraint(
            'total_count >= 0 AND correct_count >= 0 AND wrong_count >= 0',
            name='ck_study_ability_attempt_counts_nonneg',
        ),
        sa.CheckConstraint(
            'correct_count <= total_count AND wrong_count <= total_count', name='ck_study_ability_attempt_counts_logic'
        ),
        sa.CheckConstraint('duration_seconds >= 0', name='ck_study_ability_attempt_duration'),
        sa.CheckConstraint('score IS NULL OR (score >= 0 AND score <= 100)', name='ck_study_ability_attempt_score'),
        {'comment': '能力练习原始记录表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_user_account.user_id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    ability_key: Mapped[str] = mapped_column(sa.String(64), comment='能力标识')
    client_session_id: Mapped[str] = mapped_column(sa.String(64), comment='客户端会话 ID')
    mode: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='练习模式')
    difficulty: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='难度')
    source: Mapped[str] = mapped_column(sa.String(32), default='mini', comment='来源')
    study_plan_item_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_plan_item.id', ondelete='SET NULL'),
        default=None,
        comment='学习计划项 ID',
    )
    study_plan_record_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_plan_record.id', ondelete='SET NULL'),
        default=None,
        comment='学习计划完成记录 ID',
    )
    total_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='总题数')
    correct_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='正确数')
    wrong_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='错误数')
    duration_seconds: Mapped[int] = mapped_column(sa.Integer, default=0, comment='总耗时秒')
    avg_seconds: Mapped[Decimal | None] = mapped_column(sa.Numeric(8, 2), default=None, comment='平均耗时秒')
    score: Mapped[Decimal | None] = mapped_column(sa.Numeric(6, 2), default=None, comment='标准化分数')
    metric_data: Mapped[dict[str, Any] | None] = mapped_column(CompatibleJSONB, default=None, comment='特殊指标')
    records: Mapped[list[dict[str, Any]] | None] = mapped_column(CompatibleJSONB, default=None, comment='小题明细')
    completed_at: Mapped[datetime] = mapped_column(TimeZone, default_factory=timezone.now, comment='完成时间')
    completed_date: Mapped[date] = mapped_column(
        sa.Date, default_factory=lambda: timezone.now().date(), comment='完成日期'
    )

    item: Mapped[StudyPlanItem | None] = relationship(init=False, lazy='noload')
    record: Mapped[StudyPlanRecord | None] = relationship(init=False, lazy='noload')
    categories: Mapped[list[StudyAbilityAttemptCategory]] = relationship(
        init=False,
        back_populates='attempt',
        lazy='noload',
        cascade='all, delete-orphan',
    )


class StudyAbilityAttemptCategory(Base):
    """能力练习分类贡献表"""

    __tablename__ = 'study_ability_attempt_category'
    __table_args__ = (
        sa.Index('idx_study_ability_attempt_category_attempt', 'attempt_id'),
        sa.Index('idx_study_ability_attempt_category_user_cat_time', 'user_id', 'category_id', 'completed_at'),
        sa.Index('idx_study_ability_attempt_category_cat_time', 'category_id', 'completed_at'),
        sa.CheckConstraint(
            "role IN ('knowledge_point','solution_method','ability')", name='ck_study_ability_attempt_category_role'
        ),
        sa.CheckConstraint('weight > 0', name='ck_study_ability_attempt_category_weight'),
        sa.CheckConstraint('total_count >= 0 AND correct_count >= 0', name='ck_study_ability_attempt_category_counts'),
        sa.CheckConstraint('duration_seconds >= 0', name='ck_study_ability_attempt_category_duration'),
        {'comment': '能力练习分类贡献表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    attempt_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_ability_attempt.id', ondelete='CASCADE'),
        comment='练习记录 ID',
    )
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_user_account.user_id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    category_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_category.id', ondelete='RESTRICT'),
        comment='分类 ID',
    )
    completed_at: Mapped[datetime] = mapped_column(TimeZone, comment='完成时间')
    completed_date: Mapped[date] = mapped_column(sa.Date, comment='完成日期')
    role: Mapped[str] = mapped_column(sa.String(32), default='ability', comment='分类角色')
    weight: Mapped[Decimal] = mapped_column(sa.Numeric(6, 4), default=Decimal('1'), comment='权重')
    total_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='总题数')
    correct_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='正确数')
    duration_seconds: Mapped[int] = mapped_column(sa.Integer, default=0, comment='耗时秒')
    score: Mapped[Decimal | None] = mapped_column(sa.Numeric(6, 2), default=None, comment='标准化分数')

    attempt: Mapped[StudyAbilityAttempt] = relationship(init=False, back_populates='categories', lazy='noload')
    category: Mapped[Category] = relationship(init=False, lazy='noload')


class StudyUserCategoryProfile(Base):
    """用户分类画像表"""

    __tablename__ = 'study_user_category_profile'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'category_id', 'source_type', name='uq_study_user_category_profile_source'),
        sa.Index('idx_study_user_category_profile_user', 'user_id'),
        sa.Index('idx_study_user_category_profile_category', 'category_id'),
        sa.Index('idx_study_user_category_profile_mastery', 'mastery_score'),
        sa.CheckConstraint("source_type IN ('ability')", name='ck_study_user_category_profile_source'),
        sa.CheckConstraint(
            'attempt_count >= 0 AND total_count >= 0 AND correct_count >= 0',
            name='ck_study_user_category_profile_counts',
        ),
        sa.CheckConstraint('duration_seconds >= 0', name='ck_study_user_category_profile_duration'),
        {'comment': '用户分类画像表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_user_account.user_id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    category_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_category.id', ondelete='RESTRICT'),
        comment='分类 ID',
    )
    source_type: Mapped[str] = mapped_column(sa.String(32), default='ability', comment='来源类型')
    attempt_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='练习次数')
    total_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='总题数')
    correct_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='正确数')
    duration_seconds: Mapped[int] = mapped_column(sa.Integer, default=0, comment='总耗时秒')
    accuracy_rate: Mapped[Decimal] = mapped_column(sa.Numeric(6, 2), default=Decimal('0'), comment='正确率百分比')
    avg_seconds: Mapped[Decimal | None] = mapped_column(sa.Numeric(8, 2), default=None, comment='平均耗时秒')
    mastery_score: Mapped[Decimal] = mapped_column(sa.Numeric(6, 2), default=Decimal('0'), comment='掌握度')
    speed_score: Mapped[Decimal] = mapped_column(sa.Numeric(6, 2), default=Decimal('0'), comment='速度分')
    confidence_score: Mapped[Decimal] = mapped_column(sa.Numeric(6, 2), default=Decimal('0'), comment='可信度')
    trend_score: Mapped[Decimal] = mapped_column(sa.Numeric(6, 2), default=Decimal('0'), comment='趋势分')
    weakness_score: Mapped[Decimal] = mapped_column(sa.Numeric(6, 2), default=Decimal('100'), comment='薄弱度')
    last_attempt_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近练习时间')
    algorithm_version: Mapped[str] = mapped_column(sa.String(32), default='ability_profile_v1', comment='算法版本')

    category: Mapped[Category] = relationship(init=False, lazy='noload')


class StudyUserKnowledgeProfile(Base):
    """用户知识点画像表"""

    __tablename__ = 'study_user_knowledge_profile'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'knowledge_point_id', name='uq_study_user_knowledge_profile_point'),
        sa.Index('idx_study_user_knowledge_profile_user', 'user_id'),
        sa.Index('idx_study_user_knowledge_profile_point', 'knowledge_point_id'),
        sa.Index('idx_study_user_knowledge_profile_mastery', 'mastery_score'),
        sa.CheckConstraint(
            'attempt_count >= 0 AND total_count >= 0 AND correct_count >= 0',
            name='ck_study_user_knowledge_profile_counts',
        ),
        sa.CheckConstraint('duration_seconds >= 0', name='ck_study_user_knowledge_profile_duration'),
        {'comment': '用户知识点画像表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_user_account.user_id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    knowledge_point_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('qbank_v2_knowledge_point.id', ondelete='RESTRICT'),
        comment='题库 v2 知识点 ID',
    )
    attempt_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='练习次数')
    total_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='总题数')
    correct_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='正确数')
    duration_seconds: Mapped[int] = mapped_column(sa.Integer, default=0, comment='总耗时秒')
    accuracy_rate: Mapped[Decimal] = mapped_column(sa.Numeric(6, 2), default=Decimal('0'), comment='正确率百分比')
    avg_seconds: Mapped[Decimal | None] = mapped_column(sa.Numeric(8, 2), default=None, comment='平均耗时秒')
    mastery_score: Mapped[Decimal] = mapped_column(sa.Numeric(6, 2), default=Decimal('0'), comment='掌握度')
    speed_score: Mapped[Decimal] = mapped_column(sa.Numeric(6, 2), default=Decimal('0'), comment='速度分')
    confidence_score: Mapped[Decimal] = mapped_column(sa.Numeric(6, 2), default=Decimal('0'), comment='可信度')
    trend_score: Mapped[Decimal] = mapped_column(sa.Numeric(6, 2), default=Decimal('0'), comment='趋势分')
    weakness_score: Mapped[Decimal] = mapped_column(sa.Numeric(6, 2), default=Decimal('100'), comment='薄弱度')
    last_attempt_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近练习时间')
    algorithm_version: Mapped[str] = mapped_column(sa.String(32), default='ability_profile_v1', comment='算法版本')
