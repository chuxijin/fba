#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""11 节点 LLM 输出 schema, 用于 Pydantic AI Agent output_type 强类型约束.

LLM 校验失败时 pydantic_ai 自动反馈错误重试 (output_retries), 节点拿到的就是强类型对象.
"""

from typing import Literal

from pydantic import BaseModel, Field


# ──────────────────────── 复用单元类型 ────────────────────────


class MaterialPointPayload(BaseModel):
    """材料要点单元"""

    text: str = Field(min_length=2)
    weight: float = Field(default=1.0, ge=0.5, le=2.0)
    source_excerpt: str | None = None


class ReferencePointPayload(BaseModel):
    """参考答案要点单元"""

    text: str = Field(min_length=2)
    consensus_count: int = Field(ge=1)
    consensus_level: Literal['high', 'medium', 'low', 'unique']
    weight: float = Field(default=1.0, ge=0.5, le=2.0)


class AnswerPointPayload(BaseModel):
    """考生答案要点单元"""

    text: str = Field(min_length=2)
    original_excerpt: str = Field(default='')
    weight: float = Field(default=1.0, ge=0.5, le=2.0)


class MatchedPayload(BaseModel):
    """要点命中单元"""

    reference_point_text: str
    matched_user_text: str


class MissingPayload(BaseModel):
    """要点缺失单元"""

    reference_point_text: str
    consensus_level: Literal['high', 'medium', 'low', 'unique'] = 'unique'


class RubricScorePayload(BaseModel):
    """单维度评分"""

    name: str = Field(min_length=1)
    score: float = Field(ge=0)
    max_score: float = Field(gt=0)
    level: Literal['A', 'B', 'C', 'D'] | None = None
    level_label: str = ''
    comment: str = Field(default='', min_length=0)


class IssuePayload(BaseModel):
    """问题诊断单元"""

    category: str = Field(min_length=1)
    severity: Literal['critical', 'major', 'minor']
    description: str = Field(min_length=5)
    location: str | None = None
    related_section: (
        Literal[
            'score_card',
            'key_points',
            'issues',
            'suggestions',
            'rewritten_text',
            'explanations',
            'option_analysis',
            'dialogue_trace',
            'qc',
        ]
        | None
    ) = None


class SuggestionPayload(BaseModel):
    """提升建议单元"""

    target_issue: str | None = None
    action: str = Field(min_length=5)
    priority: Literal['high', 'medium', 'low'] = 'medium'


# ──────────────────────── 11 个节点 Output ────────────────────────


class ClassifierOutput(BaseModel):
    """classifier 节点输出"""

    question_type: Literal['归纳概括', '综合分析', '提出对策', '应用文', '大作文']
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=2)


class MaterialParserOutput(BaseModel):
    """material_parser 节点输出"""

    points: list[MaterialPointPayload] = Field(min_length=1)


class ReferenceAnalyzerOutput(BaseModel):
    """reference_analyzer 节点输出"""

    points: list[ReferencePointPayload] = Field(min_length=1, max_length=10)


class AnswerAnalyzerOutput(BaseModel):
    """answer_analyzer 节点输出"""

    points: list[AnswerPointPayload]


class PointMatcherOutput(BaseModel):
    """point_matcher 节点输出"""

    matched: list[MatchedPayload] = Field(default_factory=list)
    missing: list[MissingPayload] = Field(default_factory=list)


class StructureAnalyzerOutput(BaseModel):
    """structure_analyzer 节点输出"""

    paragraph_count: int = Field(ge=1)
    structure_type: str = Field(min_length=1)
    has_intro: bool
    has_conclusion: bool
    intro_quality: Literal['good', 'fair', 'poor'] | None = None
    conclusion_quality: Literal['good', 'fair', 'poor'] | None = None
    transition_issues: list[str] = Field(default_factory=list)
    summary: str = Field(min_length=5)


class ScorerOutput(BaseModel):
    """scorer 节点输出"""

    score_total: float = Field(ge=0)
    level: Literal['A', 'B', 'C', 'D']
    level_label: str = ''
    summary: str = Field(min_length=20)
    rubric_scores: list[RubricScorePayload] = Field(min_length=1)


class DiagnoserOutput(BaseModel):
    """diagnoser 节点输出"""

    issues: list[IssuePayload] = Field(min_length=1, max_length=10)


class SuggesterOutput(BaseModel):
    """suggester 节点输出"""

    suggestions: list[SuggestionPayload] = Field(min_length=1, max_length=10)


class ChangeItem(BaseModel):
    """单条改动说明"""

    original: str = Field(description='原文片段 (20-50 字)')
    revised: str = Field(description='改写片段 (20-50 字)')
    reason: str = Field(description='改动原因 (10-30 字)')


class RewriterOutput(BaseModel):
    """rewriter 节点输出"""

    revised: str = Field(min_length=10)
    diff_summary: str = Field(default='')
    changes: list[ChangeItem] = Field(default_factory=list, description='逐条改动说明')


class ReviewerOutput(BaseModel):
    """reviewer 节点输出"""

    passed: bool
    confidence: float = Field(ge=0, le=1)
    notes: list[str] = Field(default_factory=list)
