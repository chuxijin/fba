#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from pydantic import Field

from backend.common.schema import SchemaBase


class SmartCommitParam(SchemaBase):
    """智能解析提交参数"""

    bank_id: int = Field(gt=0, description='题库 ID')
    materials: list[dict[str, Any]] = Field(default_factory=list, description='材料列表')
    questions: list[dict[str, Any]] = Field(default_factory=list, description='题目列表')


class SaveSegmentsParam(SchemaBase):
    """保存分段 Markdown 参数"""

    bank_id: int = Field(gt=0, description='题库 ID')
    segments: list[dict[str, Any]] = Field(default_factory=list, description='分段列表')


class PipelineResult(SchemaBase):
    """流水线执行结果"""

    excel_url: str = Field(description='Excel 下载链接')
    questions_count: int = Field(ge=0, description='识别题目数')
    warnings_count: int = Field(ge=0, description='校验告警数')
    md_length: int = Field(ge=0, description='Markdown 原文长度')
    segments_count: int = Field(ge=0, description='分段数量')


class PreviewSegmentItem(SchemaBase):
    """分段预览项"""

    index: int = Field(ge=0, description='分段索引')
    preview: str = Field(description='预览文本（前200字）')
    length: int = Field(ge=0, description='分段长度')
    content: str = Field(description='完整分段内容')
