#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class GetStudyPlanRecordDetail(SchemaBase):
    """计划完成记录详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='记录 ID')
    item_id: int = Field(description='所属计划项 ID')
    user_id: int = Field(description='学员用户 ID')
    duration_seconds: int = Field(description='实际耗时秒数')
    score: int | None = Field(default=None, description='得分')
    correct_count: int | None = Field(default=None, description='正确题数')
    total_count: int | None = Field(default=None, description='总题数')
    extra_data: dict[str, Any] | None = Field(default=None, description='扩展数据')
    completed_at: datetime = Field(description='完成时间')
