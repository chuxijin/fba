#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any, Literal

from pydantic import Field

from backend.common.schema import SchemaBase

PracticeSourceMode = Literal['bank', 'chapter', 'chapter_type', 'knowledge_point', 'question_ids']
QuestionType = Literal['single', 'multiple', 'judgement', 'fill', 'shortAnswer']
KnowledgePointValue = str | int | dict[str, Any]


class PreviewStudyPlanPracticeSourceParam(SchemaBase):
    """刷题来源预览参数"""

    source_mode: PracticeSourceMode = Field(description='来源模式')
    bank_id: int | None = Field(default=None, gt=0, description='题库 ID')
    chapter_id: int | None = Field(default=None, gt=0, description='篇章 ID')
    cat_id: int | None = Field(default=None, gt=0, description='分类 ID')
    year_start: int | None = Field(default=None, ge=1900, le=2100, description='起始年份')
    year_end: int | None = Field(default=None, ge=1900, le=2100, description='结束年份')
    region: str | None = Field(default=None, max_length=100, description='地区关键字')
    knowledge_points: list[KnowledgePointValue] | None = Field(
        default=None,
        min_length=1,
        max_length=200,
        description='知识点条件',
    )
    question_types: list[QuestionType] | None = Field(
        default=None,
        min_length=1,
        max_length=20,
        description='题型条件',
    )
    question_ids: list[int] | None = Field(
        default=None,
        min_length=1,
        max_length=500,
        description='指定题目 ID',
    )
    question_count: int | None = Field(default=None, ge=1, le=500, description='计划抽题数量')


class PreviewStudyPlanPracticeSourceResult(SchemaBase):
    """刷题来源预览结果"""

    available_count: int = Field(ge=0, description='可用题量')
    selected_count: int = Field(ge=0, description='计划可选题量')
    sample_question_ids: list[int] = Field(default_factory=list, description='样例题目 ID')
