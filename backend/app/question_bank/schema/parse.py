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
