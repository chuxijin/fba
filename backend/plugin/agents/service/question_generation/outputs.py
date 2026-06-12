#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from pydantic import Field

from backend.common.schema import SchemaBase


class ArticleAnalysisOutput(SchemaBase):
    """文章结构分析结果"""

    global_topic: str = Field(default='', description='文章全局主题')
    paragraph_map: list[dict[str, Any]] = Field(default_factory=list, description='段落与句子结构图')
    discourse_nodes: list[dict[str, Any]] = Field(default_factory=list, description='结构节点')
    valuable_zones: list[dict[str, Any]] = Field(default_factory=list, description='潜在命题区域')
    unsuitable_zones: list[dict[str, Any]] = Field(default_factory=list, description='不宜命题区域')
    risks: list[str] = Field(default_factory=list, description='整体风险')
    confidence: float = Field(ge=0, le=1, description='置信度')


class PassagePlanItem(SchemaBase):
    """命题片段规划项"""

    passage_id: str = Field(description='片段标识')
    selected_passage: str = Field(default='', description='从文章中选取的连续命题片段')
    selected_passage_length: int = Field(default=0, ge=0, description='命题片段字数')
    selection_mode: str = Field(default='', description='选段方式')
    selected_passage_reason: str = Field(default='', description='选段理由')
    auto_selected_question_types: list[str] = Field(default_factory=list, description='自动选择题型')
    recommended_question_count: int = Field(default=1, ge=1, le=5, description='建议题量')
    recommended_types: list[str] = Field(default_factory=list, description='推荐题型')
    rejected_types: list[str] = Field(default_factory=list, description='不推荐题型')
    structure: str = Field(default='', description='文段结构')
    core_focus: str = Field(default='', description='核心落点')
    example_roles: list[dict[str, Any]] = Field(default_factory=list, description='例子功能')
    risks: list[str] = Field(default_factory=list, description='风险提示')
    confidence: float = Field(ge=0, le=1, description='置信度')


class PassageMiningOutput(SchemaBase):
    """文章选段与命题规划结果"""

    can_generate: bool = Field(description='是否适合出题')
    passages: list[PassagePlanItem] = Field(default_factory=list, description='可命题片段')
    rejected_reason: str = Field(default='', description='不可出题原因')
    risks: list[str] = Field(default_factory=list, description='整体风险提示')
    confidence: float = Field(ge=0, le=1, description='整体置信度')


class PassageReviewItem(SchemaBase):
    """片段质检项"""

    passage_id: str = Field(description='片段标识')
    decision: str = Field(description='pass/revise/discard')
    reason: str = Field(default='', description='判定理由')
    repair_instruction: str = Field(default='', description='修复指令')
    quality_flags: list[str] = Field(default_factory=list, description='质量标签')
    confidence: float = Field(ge=0, le=1, description='置信度')


class PassageReviewOutput(SchemaBase):
    """片段质检结果"""

    items: list[PassageReviewItem] = Field(default_factory=list, description='质检项')


class PassageRevisionItem(SchemaBase):
    """片段修复项"""

    passage_id: str = Field(description='片段标识')
    revised_selected_passage: str = Field(default='', description='修复后的连续片段')
    revised_question_types: list[str] = Field(default_factory=list, description='修复后题型')
    reason: str = Field(default='', description='修复说明')
    can_repair: bool = Field(default=True, description='是否可修')


class PassageRevisionOutput(SchemaBase):
    """片段修复结果"""

    items: list[PassageRevisionItem] = Field(default_factory=list, description='修复项')


class QuestionTypeOpportunityItem(SchemaBase):
    """题型机会项"""

    passage_id: str = Field(description='片段标识')
    selected_passage: str = Field(description='命题依据片段')
    selected_passage_length: int = Field(default=0, ge=0, description='片段字数')
    question_type: str = Field(description='题型')
    question_subtype: str | None = Field(default=None, description='题型细分')
    anchor: str = Field(default='', description='逻辑锚点')
    suitability_reason: str = Field(default='', description='适配理由')
    distractor_space: list[str] = Field(default_factory=list, description='干扰项空间')
    risks: list[str] = Field(default_factory=list, description='风险')
    confidence: float = Field(ge=0, le=1, description='置信度')


class QuestionTypePlanningOutput(SchemaBase):
    """题型机会规划结果"""

    items: list[QuestionTypeOpportunityItem] = Field(default_factory=list, description='题型机会')


class TypeReviewItem(SchemaBase):
    """题型质检项"""

    passage_id: str = Field(description='片段标识')
    question_type: str = Field(description='题型')
    decision: str = Field(description='pass/revise/discard')
    reason: str = Field(default='', description='判定理由')
    repair_instruction: str = Field(default='', description='修复指令')
    repaired_question_type: str | None = Field(default=None, description='修正后题型')
    confidence: float = Field(ge=0, le=1, description='置信度')


class TypeReviewOutput(SchemaBase):
    """题型质检结果"""

    items: list[TypeReviewItem] = Field(default_factory=list, description='质检项')


class BlueprintItem(SchemaBase):
    """命题蓝图"""

    passage_id: str = Field(description='片段标识')
    selected_passage: str = Field(description='命题依据片段')
    question_type: str = Field(description='题型')
    question_subtype: str | None = Field(default=None, description='题型细分')
    target_focus: str = Field(description='考查落点')
    correct_strategy: str = Field(description='正确项策略')
    distractor_strategies: list[str] = Field(min_length=3, description='干扰项策略')
    quality_requirements: list[str] = Field(default_factory=list, description='质量要求')


class BlueprintOutput(SchemaBase):
    """命题蓝图集合"""

    items: list[BlueprintItem] = Field(default_factory=list, description='蓝图列表')


class GeneratedQuestionItem(SchemaBase):
    """生成候选题"""

    passage_id: str = Field(description='片段标识')
    selected_passage: str = Field(description='命题依据片段')
    question_type: str = Field(description='题型')
    question_subtype: str | None = Field(default=None, description='题型细分')
    stem: str = Field(description='题干')
    options: list[dict[str, Any]] = Field(min_length=4, max_length=4, description='选项')
    answer_data: dict[str, Any] = Field(description='答案数据')
    analysis: str = Field(description='解析')
    blueprint: dict[str, Any] = Field(description='命题蓝图')
    difficulty: float | None = Field(default=None, ge=1, le=5, description='难度')
    knowledge_point: list[str | int | dict[str, Any]] | None = Field(default=None, description='考点标签')


class GeneratedQuestionOutput(SchemaBase):
    """生成候选题集合"""

    items: list[GeneratedQuestionItem] = Field(default_factory=list, description='候选题列表')


class QuestionReviewItem(SchemaBase):
    """成题质检项"""

    candidate_index: int = Field(ge=0, description='候选题序号')
    passage_id: str = Field(default='', description='片段标识')
    decision: str = Field(description='pass/revise/discard')
    reason: str = Field(default='', description='判定理由')
    repair_instruction: str = Field(default='', description='修复指令')
    quality_flags: list[str] = Field(default_factory=list, description='质量标签')
    confidence: float = Field(ge=0, le=1, description='置信度')


class QuestionReviewOutput(SchemaBase):
    """成题质检结果"""

    items: list[QuestionReviewItem] = Field(default_factory=list, description='质检项')

