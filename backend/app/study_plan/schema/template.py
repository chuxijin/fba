#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date, datetime
from typing import Any

from pydantic import ConfigDict, Field

from backend.app.study_plan.schema._types import ModuleType, RefType
from backend.common.schema import SchemaBase


class StudyPlanTemplateItemSchemaBase(SchemaBase):
    """模板项基础"""

    day_index: int = Field(ge=1, description='第几天')
    order_index: int = Field(ge=0, description='当天顺序')
    module_type: ModuleType = Field(description='模块类型')
    title: str = Field(min_length=1, max_length=255, description='模块标题')
    ref_type: RefType = Field(description='引用类型')
    ref_id: int | None = Field(default=None, description='引用目标 ID')
    expected_minutes: int = Field(default=15, ge=0, description='预计耗时分钟')
    extra: dict[str, Any] | None = Field(default=None, description='模块特定配置')


class CreateStudyPlanTemplateItemParam(StudyPlanTemplateItemSchemaBase):
    """创建模板项参数"""


class GetStudyPlanTemplateItemDetail(StudyPlanTemplateItemSchemaBase):
    """模板项详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='模板项 ID')
    template_id: int = Field(description='所属模板 ID')


class StudyPlanTemplateSchemaBase(SchemaBase):
    """模板基础"""

    name: str = Field(min_length=1, max_length=255, description='模板名称')
    duration_days: int = Field(ge=1, description='覆盖天数')
    domain: str = Field(default='civil_service', max_length=32, description='业务领域')
    description: str | None = Field(default=None, description='模板说明')
    is_active: bool = Field(default=True, description='是否启用')


class CreateStudyPlanTemplateParam(StudyPlanTemplateSchemaBase):
    """创建模板参数"""

    items: list[CreateStudyPlanTemplateItemParam] = Field(
        default_factory=list, description='模板项列表（可后续单独添加）',
    )


class UpdateStudyPlanTemplateParam(SchemaBase):
    """更新模板参数"""

    name: str | None = Field(default=None, min_length=1, max_length=255, description='模板名称')
    duration_days: int | None = Field(default=None, ge=1, description='覆盖天数')
    description: str | None = Field(default=None, description='模板说明')
    is_active: bool | None = Field(default=None, description='是否启用')


class GetStudyPlanTemplateDetail(StudyPlanTemplateSchemaBase):
    """模板详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='模板 ID')
    created_by: int = Field(description='创建者用户 ID')
    created_time: datetime = Field(description='创建时间')


class GetStudyPlanTemplateWithItemsDetail(GetStudyPlanTemplateDetail):
    """模板详情（含项）"""

    items: list[GetStudyPlanTemplateItemDetail] = Field(default_factory=list, description='模板项列表')


class InstantiateStudyPlanTemplateParam(SchemaBase):
    """模板实例化为计划参数"""

    template_id: int = Field(description='来源模板 ID')
    user_id: int = Field(description='目标学员用户 ID')
    title: str = Field(min_length=1, max_length=255, description='计划标题')
    start_date: date = Field(description='起始日期')
