#!/usr/bin/env python3
from typing import Any

from pydantic import Field

from backend.common.schema import SchemaBase


class ReviewMaterialItem(SchemaBase):
    """审核材料项"""

    material_id: str = Field(description='临时材料编号')
    title: str = Field(default='资料分析材料', description='材料标题')
    content: str = Field(default='', description='材料正文')
    source_segment_ids: list[str] = Field(default_factory=list, description='来源分段 ID')
    confidence: float = Field(default=0.5, ge=0, le=1, description='置信度')
    warnings: list[str] = Field(default_factory=list, description='告警列表')
    status: str = Field(default='pending_review', description='审核状态')


class ReviewQuestionItem(SchemaBase):
    """审核题目项"""

    question_id: str = Field(description='临时题目编号')
    source_segment_id: str | None = Field(default=None, description='来源分段 ID')
    question_no_raw: str | None = Field(default=None, description='原始题号')
    type: str = Field(default='single', description='题型')
    stem: str = Field(default='', description='题干')
    options_data: dict[str, Any] = Field(default_factory=dict, description='选项数据')
    answer_data: dict[str, Any] = Field(default_factory=dict, description='答案数据')
    analysis_content: str = Field(default='', description='解析内容')
    difficulty: str | None = Field(default=None, description='难度')
    knowledge_point: str | list[str] | None = Field(default=None, description='知识点')
    score: float = Field(default=1.0, description='分值')
    sort_order: int | None = Field(default=None, description='排序')
    source: str | None = Field(default=None, description='来源')
    year: int | None = Field(default=None, description='年份')
    chapter_name: str | None = Field(default=None, description='章节名')
    chapter_level1_name: str | None = Field(default=None, description='一级章节名')
    chapter_level2_name: str | None = Field(default=None, description='二级章节名')
    chapter_level3_name: str | None = Field(default=None, description='三级章节名')
    material_id: str | None = Field(default=None, description='关联临时材料编号')
    source_quote: str | None = Field(default=None, description='原文片段')
    confidence: float = Field(default=0.5, ge=0, le=1, description='置信度')
    warnings: list[str] = Field(default_factory=list, description='告警列表')
    status: str = Field(default='pending_review', description='审核状态')


class ReviewAnswerItem(SchemaBase):
    """审核解析项"""

    answer_id: str = Field(description='临时解析编号')
    source_segment_id: str | None = Field(default=None, description='来源分段 ID')
    question_no_raw: str | None = Field(default=None, description='原始题号')
    sort_order: int | None = Field(default=None, description='排序')
    answer_data: dict[str, Any] = Field(default_factory=dict, description='答案数据')
    analysis_content: str = Field(default='', description='解析内容')
    source_quote: str | None = Field(default=None, description='原文片段')
    confidence: float = Field(default=0.5, ge=0, le=1, description='置信度')
    warnings: list[str] = Field(default_factory=list, description='告警列表')
    status: str = Field(default='pending_review', description='审核状态')


class ReviewJobUpdateParam(SchemaBase):
    """审核任务更新参数"""

    materials: list[ReviewMaterialItem] = Field(default_factory=list, description='材料列表')
    questions: list[ReviewQuestionItem] = Field(default_factory=list, description='题目列表')
    answers: list[ReviewAnswerItem] = Field(default_factory=list, description='答案解析列表')
    segments: list[dict[str, Any]] = Field(default_factory=list, description='分段列表')
    status: str = Field(default='pending_review', description='任务状态')


class OCRMarkdownRecoverParam(SchemaBase):
    """OCR Markdown 恢复参数"""

    bank_id: int = Field(description='题库 ID')
    job_id: str = Field(description='云端 OCR 任务 ID')
    download_images: bool = Field(default=False, description='是否同时下载图片')


class ReviewExtractResult(SchemaBase):
    """审核抽取结果"""

    materials: list[ReviewMaterialItem] = Field(default_factory=list, description='材料列表')
    questions: list[ReviewQuestionItem] = Field(default_factory=list, description='题目列表')
    answers: list[ReviewAnswerItem] = Field(default_factory=list, description='答案解析列表')
    warnings: list[str] = Field(default_factory=list, description='全局告警')
    needs_review: bool = Field(default=True, description='是否需要人工审核')
