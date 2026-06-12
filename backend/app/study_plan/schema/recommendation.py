#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any, Literal

from pydantic import Field

from backend.app.study_plan.schema._types import ModuleType, RefType
from backend.common.schema import SchemaBase

RecommendationModuleType = Literal['ability', 'practice']


class StudyPlanItemRecommendationDraft(SchemaBase):
    """推荐计划项草稿"""

    module_type: ModuleType = Field(description='模块类型')
    title: str = Field(description='模块标题')
    ref_type: RefType = Field(description='引用类型')
    ref_id: int | None = Field(default=None, description='引用目标 ID')
    expected_minutes: int = Field(ge=0, description='预计耗时分钟')
    extra: dict[str, Any] | None = Field(default=None, description='模块特定配置')


class GetStudyPlanItemRecommendation(SchemaBase):
    """画像推荐计划项"""

    recommendation_key: str = Field(description='推荐唯一键')
    strategy: str = Field(description='推荐策略')
    strategy_version: str = Field(description='推荐策略版本')
    module_type: RecommendationModuleType = Field(description='推荐模块类型')
    category_id: int = Field(description='分类 ID')
    category_name: str | None = Field(default=None, description='分类名称')
    category_code: str | None = Field(default=None, description='分类编码')
    category_type: str | None = Field(default=None, description='分类类型')
    source_types: list[str] = Field(default_factory=list, description='画像来源')
    priority_score: float = Field(description='推荐优先级分')
    mastery_score: float = Field(description='掌握度')
    weakness_score: float = Field(description='薄弱度')
    accuracy_rate: float = Field(description='正确率百分比')
    speed_score: float = Field(description='速度分')
    confidence_score: float = Field(description='可信度')
    total_count: int = Field(description='样本题量')
    reason: str = Field(description='推荐原因')
    reason_codes: list[str] = Field(default_factory=list, description='推荐原因码')
    target_question_count: int | None = Field(default=None, description='目标题量')
    target_accuracy: float | None = Field(default=None, description='目标正确率')
    item: StudyPlanItemRecommendationDraft = Field(description='计划项草稿')
    payload: dict[str, Any] | None = Field(default=None, description='策略扩展数据')
