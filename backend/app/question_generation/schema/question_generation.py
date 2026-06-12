#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase

MaterialStatus = Literal['draft', 'usable', 'unusable', 'manual_review']
TaskStatus = Literal['pending', 'analyzing', 'planning', 'generating', 'reviewing', 'completed', 'failed']
CandidateStatus = Literal['draft', 'qc_passed', 'qc_failed', 'approved', 'published', 'rejected']


class MaterialQueryParam(SchemaBase):
    """素材查询参数"""

    exam: str | None = Field(None, max_length=64, description='考试标识')
    subject: str | None = Field(None, max_length=64, description='科目标识')
    section: str | None = Field(None, max_length=64, description='模块标识')
    status: MaterialStatus | None = Field(None, description='素材状态')
    keyword: str | None = Field(None, max_length=200, description='关键字')


class CreateMaterialParam(SchemaBase):
    """创建素材参数"""

    title: str = Field(min_length=1, max_length=255, description='素材标题')
    content: str = Field(min_length=1, description='素材正文')
    source: str | None = Field(None, max_length=255, description='素材来源')
    source_url: str | None = Field(None, max_length=500, description='来源链接')
    source_publish_time: datetime | None = Field(None, description='来源发布时间')
    exam: str = Field(default='gk', max_length=64, description='考试标识')
    subject: str = Field(default='xingce', max_length=64, description='科目标识')
    section: str = Field(default='yuyan', max_length=64, description='模块标识')
    province: str | None = Field(None, max_length=64, description='地区标识')
    year: int | None = Field(None, ge=1900, le=2100, description='素材年份')
    tags: list[str] | None = Field(None, max_length=100, description='素材标签')


class UpdateMaterialParam(CreateMaterialParam):
    """更新素材参数"""

    status: MaterialStatus = Field(default='draft', description='素材状态')


class DeleteMaterialParam(SchemaBase):
    """删除素材参数"""

    ids: list[int] = Field(min_length=1, description='素材 ID 列表')


class DeleteTaskParam(SchemaBase):
    """删除任务参数"""

    ids: list[int] = Field(min_length=1, description='任务 ID 列表')


class DeleteCandidateParam(SchemaBase):
    """删除候选题参数"""

    ids: list[int] = Field(min_length=1, description='候选题 ID 列表')


class GetMaterialListItem(SchemaBase):
    """素材列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='素材 ID')
    title: str = Field(description='素材标题')
    source: str | None = Field(None, description='素材来源')
    source_publish_time: datetime | None = Field(None, description='来源发布时间')
    exam: str = Field(description='考试标识')
    subject: str = Field(description='科目标识')
    section: str = Field(description='模块标识')
    province: str | None = Field(None, description='地区标识')
    year: int | None = Field(None, description='素材年份')
    tags: list[str] | None = Field(None, description='素材标签')
    status: MaterialStatus = Field(description='素材状态')
    processed_time: datetime | None = Field(None, description='处理时间')
    created_time: datetime = Field(description='创建时间')


class GetMaterialDetail(GetMaterialListItem):
    """素材详情"""

    content: str = Field(description='素材正文')
    source_url: str | None = Field(None, description='来源链接')
    process_result: dict[str, Any] | None = Field(None, description='素材处理结果')


class StartGenerationParam(SchemaBase):
    """启动出题参数"""

    material_id: int = Field(gt=0, description='素材 ID')
    user_id: int = Field(gt=0, description='提交用户 ID')
    provider_id: int = Field(default=5, gt=0, description='AI 供应商 ID')
    model_id: str = Field(default='mimo-v2.5-pro', max_length=128, description='主力模型 ID')
    mini_model_id: str | None = Field(None, max_length=128, description='经济模型 ID')
    exam: str = Field(default='gk', max_length=64, description='考试标识')
    subject: str = Field(default='xingce', max_length=64, description='科目标识')
    section: str = Field(default='yuyan', max_length=64, description='模块标识')
    target_question_types: list[str] | None = Field(None, max_length=20, description='系统字段，调用方传入会被忽略')
    question_count: int = Field(default=1, ge=1, le=10, description='系统字段，调用方传入会被忽略')


class StartGenerationResult(SchemaBase):
    """启动出题结果"""

    task_id: int = Field(description='任务 ID')
    status: TaskStatus = Field(description='任务状态')


class GenerationTaskListItem(SchemaBase):
    """出题任务列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='任务 ID')
    material_id: int = Field(description='素材 ID')
    user_id: int = Field(description='提交用户 ID')
    exam: str = Field(description='考试标识')
    subject: str = Field(description='科目标识')
    section: str = Field(description='模块标识')
    target_question_types: list[str] | None = Field(None, description='目标题型')
    question_count: int = Field(description='目标题量')
    status: TaskStatus = Field(description='任务状态')
    stage: str | None = Field(None, description='当前阶段')
    progress: float = Field(description='进度 0-1')
    error_code: str | None = Field(None, description='错误码')
    error_message: str | None = Field(None, description='错误信息')
    created_time: datetime = Field(description='创建时间')
    finished_time: datetime | None = Field(None, description='结束时间')


class GenerationTaskDetail(GenerationTaskListItem):
    """出题任务详情"""

    input_payload: dict[str, Any] = Field(description='输入参数')
    state_snapshot: dict[str, Any] | None = Field(None, description='中间快照')
    result_summary: dict[str, Any] | None = Field(None, description='结果摘要')


class CandidateListItem(SchemaBase):
    """候选题列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='候选题 ID')
    task_id: int = Field(description='任务 ID')
    material_id: int = Field(description='素材 ID')
    status: CandidateStatus = Field(description='候选题状态')
    passage_id: str | None = Field(None, description='片段标识')
    question_type: str = Field(description='题型')
    question_subtype: str | None = Field(None, description='题型细分')
    difficulty: Decimal | None = Field(None, description='难度')
    sort_order: int = Field(description='排序')
    published_question_id: int | None = Field(None, description='发布后的题目 ID')
    created_time: datetime = Field(description='创建时间')


class GetCandidateDetail(CandidateListItem):
    """候选题详情"""

    selected_passage: str = Field(description='命题依据片段')
    passage_meta: dict[str, Any] | None = Field(None, description='片段元信息')
    stem: str = Field(description='题干')
    options: list[dict[str, Any]] = Field(description='选项列表')
    answer_data: dict[str, Any] = Field(description='答案数据')
    analysis: str = Field(description='解析')
    blueprint: dict[str, Any] | None = Field(None, description='命题蓝图')
    qc_result: dict[str, Any] | None = Field(None, description='质检结果')
    knowledge_point: list[str | int | dict[str, Any]] | None = Field(None, description='考点标签')


class CandidateReviewParam(SchemaBase):
    """候选题审核参数"""

    status: Literal['approved', 'rejected'] = Field(description='审核状态')
    reason: str | None = Field(None, max_length=500, description='审核原因')
