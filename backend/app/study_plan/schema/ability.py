#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any, Literal

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class GetStudyPlanAbilityCatalogItem(SchemaBase):
    """能力目录项"""

    id: int | None = Field(default=None, description='目录 ID')
    key: str = Field(description='能力标识')
    title: str = Field(description='能力名称')
    description: str = Field(description='能力说明')
    domain: str = Field(description='业务领域')
    category: str = Field(description='能力分类')
    url: str = Field(description='小程序入口 URL')
    default_minutes: int = Field(ge=0, description='默认预计分钟')
    default_question_count: int | None = Field(default=None, ge=1, description='默认题数')
    default_accuracy: float | None = Field(default=None, ge=0, le=1, description='默认正确率')
    benchmark_seconds: float | None = Field(default=None, gt=0, description='速度基准秒')
    supports_study_plan: bool = Field(description='是否支持学习计划')
    supports_result: bool = Field(description='是否支持自动结算')
    is_active: bool = Field(default=True, description='是否启用')
    is_persisted: bool = Field(default=False, description='是否已落库')
    extra: dict[str, Any] | None = Field(default=None, description='扩展配置')


class CreateStudyAbilityCatalogParam(SchemaBase):
    """创建能力目录"""

    ability_key: str = Field(min_length=1, max_length=64, description='能力标识')
    title: str = Field(min_length=1, max_length=128, description='能力名称')
    category: str = Field(min_length=1, max_length=64, description='能力分类')
    url: str = Field(min_length=1, max_length=512, description='小程序入口 URL')
    domain: str = Field(default='civil_service', max_length=32, description='业务领域')
    description: str | None = Field(default=None, max_length=512, description='能力说明')
    default_minutes: int = Field(default=0, ge=0, description='默认预计分钟')
    default_question_count: int | None = Field(default=None, ge=1, description='默认题数')
    default_accuracy: float | None = Field(default=None, ge=0, le=1, description='默认正确率')
    benchmark_seconds: float | None = Field(default=None, gt=0, description='速度基准秒')
    supports_study_plan: bool = Field(default=True, description='是否支持学习计划')
    supports_result: bool = Field(default=True, description='是否支持自动结算')
    is_active: bool = Field(default=True, description='是否启用')
    extra: dict[str, Any] | None = Field(default=None, description='扩展配置')


class UpdateStudyAbilityCatalogParam(SchemaBase):
    """更新能力目录"""

    title: str | None = Field(default=None, min_length=1, max_length=128, description='能力名称')
    category: str | None = Field(default=None, min_length=1, max_length=64, description='能力分类')
    url: str | None = Field(default=None, min_length=1, max_length=512, description='小程序入口 URL')
    domain: str | None = Field(default=None, max_length=32, description='业务领域')
    description: str | None = Field(default=None, max_length=512, description='能力说明')
    default_minutes: int | None = Field(default=None, ge=0, description='默认预计分钟')
    default_question_count: int | None = Field(default=None, ge=1, description='默认题数')
    default_accuracy: float | None = Field(default=None, ge=0, le=1, description='默认正确率')
    benchmark_seconds: float | None = Field(default=None, gt=0, description='速度基准秒')
    supports_study_plan: bool | None = Field(default=None, description='是否支持学习计划')
    supports_result: bool | None = Field(default=None, description='是否支持自动结算')
    is_active: bool | None = Field(default=None, description='是否启用')
    extra: dict[str, Any] | None = Field(default=None, description='扩展配置')


StudyAbilityBindingRole = Literal['knowledge_point', 'solution_method', 'ability']


class CreateStudyAbilityCategoryBindingParam(SchemaBase):
    """创建能力分类绑定"""

    ability_key: str = Field(min_length=1, max_length=64, description='能力标识')
    mode: str | None = Field(default=None, max_length=64, description='练习模式')
    category_id: int = Field(gt=0, description='分类 ID')
    role: StudyAbilityBindingRole = Field(default='ability', description='绑定角色')
    weight: float = Field(default=1, gt=0, le=10, description='权重')
    is_primary: bool = Field(default=False, description='是否主分类')
    source: str = Field(default='manual', max_length=32, description='来源')
    confidence: float = Field(default=1, ge=0, le=1, description='置信度')


class UpdateStudyAbilityCategoryBindingParam(SchemaBase):
    """更新能力分类绑定"""

    mode: str | None = Field(default=None, max_length=64, description='练习模式')
    category_id: int | None = Field(default=None, gt=0, description='分类 ID')
    role: StudyAbilityBindingRole | None = Field(default=None, description='绑定角色')
    weight: float | None = Field(default=None, gt=0, le=10, description='权重')
    is_primary: bool | None = Field(default=None, description='是否主分类')
    source: str | None = Field(default=None, max_length=32, description='来源')
    confidence: float | None = Field(default=None, ge=0, le=1, description='置信度')


class GetStudyAbilityCategoryBindingDetail(SchemaBase):
    """能力分类绑定详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='绑定 ID')
    ability_key: str = Field(description='能力标识')
    mode: str | None = Field(default=None, description='练习模式')
    category_id: int = Field(description='分类 ID')
    category_name: str | None = Field(default=None, description='分类名称')
    category_code: str | None = Field(default=None, description='分类编码')
    category_type: str | None = Field(default=None, description='分类类型')
    role: str = Field(description='绑定角色')
    weight: float = Field(description='权重')
    is_primary: bool = Field(description='是否主分类')
    source: str = Field(description='来源')
    confidence: float = Field(description='置信度')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(default=None, description='更新时间')


class SubmitStudyAbilityAttemptParam(SchemaBase):
    """提交能力练习记录"""

    ability_key: str = Field(min_length=1, max_length=64, description='能力标识')
    ability_title: str | None = Field(default=None, max_length=128, description='能力名称快照')
    mode: str | None = Field(default=None, max_length=64, description='练习模式')
    difficulty: str | None = Field(default=None, max_length=32, description='难度')
    source: str = Field(default='mini', max_length=32, description='来源')
    study_plan_item_id: int | None = Field(default=None, description='学习计划项 ID')
    client_session_id: str = Field(min_length=1, max_length=64, description='客户端会话 ID')
    total_count: int = Field(ge=0, description='总题数')
    correct_count: int = Field(ge=0, description='正确题数')
    wrong_count: int | None = Field(default=None, ge=0, description='错误题数')
    duration_seconds: int = Field(ge=0, description='总耗时秒')
    avg_seconds: float | None = Field(default=None, ge=0, description='平均耗时秒')
    score: float | None = Field(default=None, ge=0, le=100, description='标准化分数')
    metric_data: dict[str, Any] | None = Field(default=None, description='特殊指标')
    records: list[dict[str, Any]] | None = Field(default=None, description='小题明细')
    completed_at: datetime | None = Field(default=None, description='完成时间')


class BatchSubmitStudyAbilityAttemptParam(SchemaBase):
    """批量提交能力练习记录"""

    attempts: list[SubmitStudyAbilityAttemptParam] = Field(default_factory=list, description='能力练习记录')


class GetStudyAbilityAttemptDetail(SchemaBase):
    """能力练习记录详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='记录 ID')
    user_id: int = Field(description='用户 ID')
    ability_key: str = Field(description='能力标识')
    mode: str | None = Field(default=None, description='练习模式')
    difficulty: str | None = Field(default=None, description='难度')
    source: str = Field(description='来源')
    study_plan_item_id: int | None = Field(default=None, description='学习计划项 ID')
    study_plan_record_id: int | None = Field(default=None, description='学习计划完成记录 ID')
    client_session_id: str = Field(description='客户端会话 ID')
    total_count: int = Field(description='总题数')
    correct_count: int = Field(description='正确题数')
    wrong_count: int = Field(description='错误题数')
    duration_seconds: int = Field(description='总耗时秒')
    avg_seconds: float | None = Field(default=None, description='平均耗时秒')
    score: float | None = Field(default=None, description='标准化分数')
    metric_data: dict[str, Any] | None = Field(default=None, description='特殊指标')
    records: list[dict[str, Any]] | None = Field(default=None, description='小题明细')
    completed_at: datetime = Field(description='完成时间')
    created_time: datetime = Field(description='创建时间')


class SubmitStudyAbilityAttemptResult(SchemaBase):
    """能力练习提交结果"""

    attempt: GetStudyAbilityAttemptDetail = Field(description='能力练习记录')
    profile_updated_count: int = Field(description='更新画像节点数')
    study_plan_synced: bool = Field(description='是否已同步学习计划')
    study_plan_error: str | None = Field(default=None, description='学习计划同步错误')


class BatchSubmitStudyAbilityAttemptResult(SchemaBase):
    """批量提交能力练习结果"""

    total: int = Field(description='提交总数')
    results: list[SubmitStudyAbilityAttemptResult] = Field(default_factory=list, description='提交结果')


class GetStudyUserCategoryProfileDetail(SchemaBase):
    """用户分类画像详情"""

    id: int = Field(description='画像 ID')
    user_id: int = Field(description='用户 ID')
    category_id: int = Field(description='分类 ID')
    category_name: str | None = Field(default=None, description='分类名称')
    category_code: str | None = Field(default=None, description='分类编码')
    category_type: str | None = Field(default=None, description='分类类型')
    source_type: str = Field(description='来源类型')
    attempt_count: int = Field(description='练习次数')
    total_count: int = Field(description='总题数')
    correct_count: int = Field(description='正确题数')
    duration_seconds: int = Field(description='总耗时秒')
    accuracy_rate: float = Field(description='正确率百分比')
    avg_seconds: float | None = Field(default=None, description='平均耗时秒')
    mastery_score: float = Field(description='掌握度')
    speed_score: float = Field(description='速度分')
    confidence_score: float = Field(description='可信度')
    trend_score: float = Field(description='趋势分')
    weakness_score: float = Field(description='薄弱度')
    last_attempt_at: datetime | None = Field(default=None, description='最近练习时间')
    algorithm_version: str = Field(description='算法版本')
    updated_time: datetime | None = Field(default=None, description='更新时间')
