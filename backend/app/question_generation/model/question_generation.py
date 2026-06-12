#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa

from sqlalchemy.dialects.mysql import JSON as MySQLJSON
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.enums import DataBaseType
from backend.common.model import Base, TimeZone, UniversalText, UserMixin, id_key
from backend.core.conf import settings

JSONType = JSONB if DataBaseType.postgresql == settings.DATABASE_TYPE else MySQLJSON

if TYPE_CHECKING:
    from backend.app.question_bank.model.question import Question


class QuestionGenerationMaterial(Base, UserMixin):
    """AI 出题素材表"""

    __tablename__ = 'ai_question_generation_material'
    __table_args__ = (
        sa.Index('idx_ai_qg_material_scope', 'exam', 'subject', 'section'),
        sa.Index('idx_ai_qg_material_status', 'status'),
        sa.Index('idx_ai_qg_material_source', 'source'),
        {'comment': 'AI 出题素材表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    title: Mapped[str] = mapped_column(sa.String(255), comment='素材标题')
    content: Mapped[str] = mapped_column(UniversalText, comment='素材正文')
    source: Mapped[str | None] = mapped_column(sa.String(255), default=None, comment='素材来源')
    source_url: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='来源链接')
    source_publish_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='来源发布时间')
    exam: Mapped[str] = mapped_column(sa.String(64), default='gk', comment='考试标识')
    subject: Mapped[str] = mapped_column(sa.String(64), default='xingce', comment='科目标识')
    section: Mapped[str] = mapped_column(sa.String(64), default='yuyan', comment='模块标识')
    province: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='地区标识')
    year: Mapped[int | None] = mapped_column(sa.SmallInteger, default=None, comment='素材年份')
    tags: Mapped[list[str] | None] = mapped_column(JSONType, default=None, comment='素材标签')
    status: Mapped[str] = mapped_column(
        sa.String(32),
        default='draft',
        comment='状态: draft/usable/unusable/manual_review',
    )
    process_result: Mapped[dict[str, Any] | None] = mapped_column(JSONType, default=None, comment='素材处理结果')
    processed_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='处理时间')

    tasks: Mapped[list['QuestionGenerationTask']] = relationship(
        init=False,
        back_populates='material',
        lazy='noload',
    )
    candidates: Mapped[list['QuestionGenerationCandidate']] = relationship(
        init=False,
        back_populates='material',
        lazy='noload',
    )


class QuestionGenerationTask(Base, UserMixin):
    """AI 出题任务表"""

    __tablename__ = 'ai_question_generation_task'
    __table_args__ = (
        sa.Index('idx_ai_qg_task_material', 'material_id'),
        sa.Index('idx_ai_qg_task_status', 'status'),
        sa.Index('idx_ai_qg_task_scope', 'exam', 'subject', 'section'),
        {'comment': 'AI 出题任务表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    material_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('ai_question_generation_material.id', ondelete='CASCADE'),
        comment='素材 ID',
    )
    user_id: Mapped[int] = mapped_column(sa.BigInteger, comment='提交用户 ID')
    provider_id: Mapped[int] = mapped_column(sa.BigInteger, comment='AI 供应商 ID')
    model_id: Mapped[str] = mapped_column(sa.String(128), comment='主力模型 ID')
    input_payload: Mapped[dict[str, Any]] = mapped_column(JSONType, comment='输入参数')
    mini_model_id: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='经济模型 ID')
    exam: Mapped[str] = mapped_column(sa.String(64), default='gk', comment='考试标识')
    subject: Mapped[str] = mapped_column(sa.String(64), default='xingce', comment='科目标识')
    section: Mapped[str] = mapped_column(sa.String(64), default='yuyan', comment='模块标识')
    target_question_types: Mapped[list[str] | None] = mapped_column(JSONType, default=None, comment='目标题型')
    question_count: Mapped[int] = mapped_column(sa.SmallInteger, default=1, comment='目标题量')
    status: Mapped[str] = mapped_column(
        sa.String(32),
        default='pending',
        comment='状态: pending/analyzing/planning/generating/reviewing/completed/failed',
    )
    stage: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='当前阶段')
    progress: Mapped[float] = mapped_column(sa.Float, default=0.0, comment='进度 0-1')
    state_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSONType, default=None, comment='中间快照')
    result_summary: Mapped[dict[str, Any] | None] = mapped_column(JSONType, default=None, comment='结果摘要')
    error_code: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='错误码')
    error_message: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='错误信息')
    started_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='开始时间')
    finished_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='结束时间')

    material: Mapped[QuestionGenerationMaterial] = relationship(
        init=False,
        back_populates='tasks',
        lazy='noload',
    )
    candidates: Mapped[list['QuestionGenerationCandidate']] = relationship(
        init=False,
        back_populates='task',
        lazy='noload',
        cascade='all, delete-orphan',
    )


class QuestionGenerationCandidate(Base, UserMixin):
    """AI 候选题表"""

    __tablename__ = 'ai_question_generation_candidate'
    __table_args__ = (
        sa.Index('idx_ai_qg_candidate_task', 'task_id'),
        sa.Index('idx_ai_qg_candidate_material', 'material_id'),
        sa.Index('idx_ai_qg_candidate_status', 'status'),
        sa.Index('idx_ai_qg_candidate_type', 'question_type', 'question_subtype'),
        {'comment': 'AI 候选题表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    task_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('ai_question_generation_task.id', ondelete='CASCADE'),
        comment='任务 ID',
    )
    material_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('ai_question_generation_material.id', ondelete='CASCADE'),
        comment='素材 ID',
    )
    question_type: Mapped[str] = mapped_column(sa.String(64), comment='题型')
    selected_passage: Mapped[str] = mapped_column(UniversalText, comment='命题依据片段')
    stem: Mapped[str] = mapped_column(UniversalText, comment='题干')
    options: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, comment='选项列表')
    answer_data: Mapped[dict[str, Any]] = mapped_column(JSONType, comment='答案数据')
    analysis: Mapped[str] = mapped_column(UniversalText, comment='解析')
    passage_id: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='片段标识')
    status: Mapped[str] = mapped_column(
        sa.String(32),
        default='draft',
        comment='状态: draft/qc_passed/qc_failed/approved/published/rejected',
    )
    question_subtype: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='题型细分')
    passage_meta: Mapped[dict[str, Any] | None] = mapped_column(JSONType, default=None, comment='片段元信息')
    blueprint: Mapped[dict[str, Any] | None] = mapped_column(JSONType, default=None, comment='命题蓝图')
    qc_result: Mapped[dict[str, Any] | None] = mapped_column(JSONType, default=None, comment='质检结果')
    difficulty: Mapped[Decimal | None] = mapped_column(sa.Numeric(3, 1), default=None, comment='难度')
    knowledge_point: Mapped[list[str | int | dict[str, Any]] | None] = mapped_column(
        JSONType,
        default=None,
        comment='考点标签',
    )
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='排序')
    published_question_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_question.id', ondelete='SET NULL'),
        default=None,
        comment='发布后的题目 ID',
    )
    published_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='发布时间')

    task: Mapped[QuestionGenerationTask] = relationship(
        init=False,
        back_populates='candidates',
        lazy='noload',
    )
    material: Mapped[QuestionGenerationMaterial] = relationship(
        init=False,
        back_populates='candidates',
        lazy='noload',
    )
    published_question: Mapped['Question | None'] = relationship(init=False, lazy='noload')
