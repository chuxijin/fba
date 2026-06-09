#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date, datetime

from pydantic import ConfigDict, Field

from backend.app.study_plan.schema._types import PlanStatus
from backend.common.schema import SchemaBase


class StudyPlanSchemaBase(SchemaBase):
    """学习计划基础"""

    title: str = Field(min_length=1, max_length=255, description='计划标题')
    start_date: date = Field(description='起始日期')
    end_date: date = Field(description='结束日期')
    domain: str = Field(default='civil_service', max_length=32, description='业务领域')


class CreateStudyPlanParam(StudyPlanSchemaBase):
    """创建学习计划参数"""

    user_id: int = Field(description='学员用户 ID')
    template_id: int | None = Field(default=None, description='来源模板 ID')


class UpdateStudyPlanParam(SchemaBase):
    """更新学习计划参数"""

    title: str | None = Field(default=None, min_length=1, max_length=255, description='计划标题')
    start_date: date | None = Field(default=None, description='起始日期')
    end_date: date | None = Field(default=None, description='结束日期')
    status: PlanStatus | None = Field(default=None, description='状态')


class GetStudyPlanDetail(StudyPlanSchemaBase):
    """学习计划详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='计划 ID')
    user_id: int = Field(description='学员用户 ID')
    status: PlanStatus = Field(description='状态')
    template_id: int | None = Field(default=None, description='来源模板 ID')
    created_by: int = Field(description='创建者用户 ID')
    created_time: datetime = Field(description='创建时间')


class StudyPlanProgress(SchemaBase):
    """计划进度"""

    completed: int = Field(description='已完成项数')
    total: int = Field(description='总项数')
    percent: int = Field(ge=0, le=100, description='完成百分比')
