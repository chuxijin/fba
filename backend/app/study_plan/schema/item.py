#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date, datetime
from typing import Any

from pydantic import ConfigDict, Field

from backend.app.study_plan.schema._types import ItemStatus, ModuleType, RefType
from backend.common.schema import SchemaBase


class StudyPlanItemSchemaBase(SchemaBase):
    """学习计划项基础"""

    plan_date: date = Field(description='所属日期')
    order_index: int = Field(ge=0, description='当日顺序')
    module_type: ModuleType = Field(description='模块类型')
    title: str = Field(min_length=1, max_length=255, description='模块标题')
    ref_type: RefType = Field(description='引用类型')
    ref_id: int | None = Field(default=None, description='引用目标 ID')
    expected_minutes: int = Field(default=15, ge=0, description='预计耗时分钟')
    extra: dict[str, Any] | None = Field(default=None, description='模块特定配置')


class CreateStudyPlanItemParam(StudyPlanItemSchemaBase):
    """创建计划项参数"""

    plan_id: int = Field(description='所属计划 ID')


class UpdateStudyPlanItemParam(SchemaBase):
    """更新计划项参数"""

    plan_date: date | None = Field(default=None, description='所属日期')
    order_index: int | None = Field(default=None, ge=0, description='当日顺序')
    module_type: ModuleType | None = Field(default=None, description='模块类型')
    title: str | None = Field(default=None, min_length=1, max_length=255, description='模块标题')
    ref_type: RefType | None = Field(default=None, description='引用类型')
    ref_id: int | None = Field(default=None, description='引用目标 ID')
    expected_minutes: int | None = Field(default=None, ge=0, description='预计耗时分钟')
    extra: dict[str, Any] | None = Field(default=None, description='模块特定配置')
    status: ItemStatus | None = Field(default=None, description='状态')


class GetStudyPlanItemDetail(StudyPlanItemSchemaBase):
    """计划项详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='计划项 ID')
    plan_id: int = Field(description='所属计划 ID')
    user_id: int = Field(description='学员用户 ID')
    status: ItemStatus = Field(description='状态')
    created_time: datetime = Field(description='创建时间')


class StartStudyPlanItemResult(SchemaBase):
    """启动计划项返回"""

    item_id: int = Field(description='计划项 ID')
    status: ItemStatus = Field(description='更新后的状态')
    payload: dict[str, Any] | None = Field(
        default=None,
        description='模块启动所需数据（如错题复盘的题目 ID 列表、刷题任务的题目集合）',
    )


class CompleteStudyPlanItemParam(SchemaBase):
    """提交计划项完成参数"""

    duration_seconds: int = Field(default=0, ge=0, description='本次耗时秒数')
    score: int | None = Field(default=None, ge=0, description='得分（刷题类）')
    correct_count: int | None = Field(default=None, ge=0, description='正确题数（刷题类）')
    total_count: int | None = Field(default=None, ge=0, description='总题数（刷题类）')
    read_acknowledged: bool | None = Field(default=None, description='复习类已读确认')
    extra_data: dict[str, Any] | None = Field(default=None, description='扩展数据')
