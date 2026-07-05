#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pydantic import Field

from backend.app.gongkao.schema.practice_log import CreatePracticeModuleParam
from backend.common.schema import SchemaBase


class ImportPracticeLogVisionParam(SchemaBase):
    """AI 智能导入练习记录参数"""

    image_base64: str = Field(description='图片 base64 数据（不含 data:image/... 前缀）')
    prompt: str | None = Field(default=None, description='自定义提示词，覆盖默认')
    provider_id: int | None = Field(default=None, description='AI 供应商 ID（不传则使用默认）')
    model_id: str | None = Field(default=None, description='AI 模型 ID（不传则使用默认）')


class ImportPracticeLogVisionResult(SchemaBase):
    """AI 智能导入结果"""

    material_type: str = Field(description='材料类型（exam/practice/special）')
    material_title: str = Field(description='练习材料标题')
    total_questions: int = Field(description='总题数')
    correct_count: int = Field(description='正确数')
    duration_seconds: int | None = Field(None, description='用时（秒）')
    modules: list[CreatePracticeModuleParam] = Field(default_factory=list, description='模块明细')
    raw_raw: str | None = Field(None, description='AI 原始返回')
