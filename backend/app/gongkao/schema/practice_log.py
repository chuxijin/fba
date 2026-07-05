#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date, datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class CreatePracticeModuleParam(SchemaBase):
    """创建练习模块参数"""

    module_name: str = Field(description='模块名称', min_length=1, max_length=100)
    total_questions: int = Field(description='该模块题数', ge=1)
    correct_count: int = Field(description='该模块正确数', ge=0)
    duration_seconds: int | None = Field(None, description='该模块用时（分钟）', ge=0)
    seq_no: int = Field(default=0, description='排序序号')


class CreatePracticeLogParam(SchemaBase):
    """创建练习记录参数"""

    material_type: str = Field(default='exam', description='材料类型（exam 模考, practice 练习, special 专项）')
    material_title: str = Field(description='练习材料标题', min_length=1, max_length=200)
    total_questions: int = Field(description='总题数', ge=1)
    correct_count: int = Field(description='正确数', ge=0)
    duration_seconds: int | None = Field(None, description='练习用时（分钟）', ge=0)
    practiced_at: date = Field(description='练习日期')
    remark: str | None = Field(None, description='备注')
    modules: list[CreatePracticeModuleParam] = Field(default_factory=list, description='模块列表')


class UpdatePracticeModuleParam(SchemaBase):
    """更新练习模块参数"""

    module_name: str = Field(description='模块名称', min_length=1, max_length=100)
    total_questions: int = Field(description='该模块题数', ge=1)
    correct_count: int = Field(description='该模块正确数', ge=0)
    duration_seconds: int | None = Field(None, description='该模块用时（分钟）', ge=0)
    seq_no: int = Field(default=0, description='排序序号')


class UpdatePracticeLogParam(SchemaBase):
    """更新练习记录参数"""

    material_type: str | None = Field(None, description='材料类型（exam 模考, practice 练习, special 专项）')
    material_title: str | None = Field(None, description='练习材料标题', min_length=1, max_length=200)
    total_questions: int | None = Field(None, description='总题数', ge=1)
    correct_count: int | None = Field(None, description='正确数', ge=0)
    duration_seconds: int | None = Field(None, description='练习用时（分钟）', ge=0)
    practiced_at: date | None = Field(None, description='练习日期')
    remark: str | None = Field(None, description='备注')
    modules: list[UpdatePracticeModuleParam] | None = Field(None, description='模块列表')


class GetPracticeModuleDetail(SchemaBase):
    """练习模块详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='模块 ID')
    module_name: str = Field(description='模块名称')
    total_questions: int = Field(description='该模块题数')
    correct_count: int = Field(description='该模块正确数')
    accuracy_rate: float | None = Field(None, description='该模块正确率（%）')
    duration_seconds: int | None = Field(None, description='该模块用时（分钟）')
    seq_no: int = Field(description='排序序号')


class GetPracticeLogDetail(SchemaBase):
    """练习记录详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='练习记录 ID')
    user_id: int = Field(description='用户 ID')
    material_type: str = Field(description='材料类型')
    material_title: str = Field(description='练习材料标题')
    total_questions: int = Field(description='总题数')
    correct_count: int = Field(description='正确数')
    accuracy_rate: float | None = Field(None, description='正确率（%）')
    duration_seconds: int | None = Field(None, description='练习用时（分钟）')
    practiced_at: date = Field(description='练习日期')
    remark: str | None = Field(None, description='备注')
    modules: list[GetPracticeModuleDetail] = Field(default_factory=list, description='模块列表')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetPracticeLogListItem(GetPracticeLogDetail):
    """练习记录列表项"""

    module_count: int = Field(default=0, description='模块数量')
