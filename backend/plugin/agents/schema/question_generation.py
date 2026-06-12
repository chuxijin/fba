#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from pydantic import Field

from backend.common.schema import SchemaBase
from backend.plugin.agents.schema.report import AgentTraceItem


class QuestionGenerationState(SchemaBase):
    """AI 出题状态"""

    task_id: int = Field(description='任务 ID')
    user_id: int = Field(description='提交用户 ID')
    provider_id: int = Field(description='AI 供应商 ID')
    primary_model: str = Field(description='主力模型 ID')
    material_id: int = Field(description='素材 ID')
    material_title: str = Field(description='素材标题')
    material_content: str = Field(description='素材正文')
    selected_passages: list[dict[str, Any]] = Field(default_factory=list, description='命题依据片段列表')
    exam: str = Field(default='gk', description='考试标识')
    subject: str = Field(default='xingce', description='科目标识')
    section: str = Field(default='yuyan', description='模块标识')
    target_question_types: list[str] | None = Field(default=None, description='目标题型')
    question_count: int = Field(default=1, description='目标题量')
    profile: dict[str, Any] | None = Field(default=None, description='命题规则画像')
    article_analysis: dict[str, Any] | None = Field(default=None, description='文章结构分析')
    passage_plan: dict[str, Any] | None = Field(default=None, description='选段与命题规划')
    passage_reviews: list[dict[str, Any]] = Field(default_factory=list, description='片段质检记录')
    discarded_passages: list[dict[str, Any]] = Field(default_factory=list, description='舍弃片段记录')
    question_type_opportunities: list[dict[str, Any]] = Field(default_factory=list, description='题型机会列表')
    type_reviews: list[dict[str, Any]] = Field(default_factory=list, description='题型质检记录')
    discarded_type_opportunities: list[dict[str, Any]] = Field(default_factory=list, description='舍弃题型机会记录')
    blueprints: list[dict[str, Any]] = Field(default_factory=list, description='命题蓝图')
    candidates: list[dict[str, Any]] = Field(default_factory=list, description='候选题')
    question_reviews: list[dict[str, Any]] = Field(default_factory=list, description='成题质检记录')
    discarded_candidates: list[dict[str, Any]] = Field(default_factory=list, description='舍弃候选题记录')
    qc: dict[str, Any] | None = Field(default=None, description='质检结果')
    traces: list[AgentTraceItem] = Field(default_factory=list, description='执行轨迹')
    extras: dict[str, Any] = Field(default_factory=dict, description='节点临时数据')
    started_at: datetime = Field(default_factory=datetime.now, description='开始时间')
