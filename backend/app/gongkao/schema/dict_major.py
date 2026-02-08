#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class DictMajorSchemaBase(SchemaBase):
    """专业目录基础"""

    code: str = Field(description='专业代码')
    name: str = Field(description='专业名称')
    level: int = Field(description='级别: 1学科门类 2专业类 3专业')
    parent_code: str | None = Field(None, description='父级代码')
    edu_level: str = Field(default='本科', description='学历层次: 本科/研究生')
    aliases: list[str] | None = Field(None, description='专业别名列表')
    description: str | None = Field(None, description='专业说明')
    sort_order: int = Field(default=0, description='排序')
    is_active: bool = Field(default=True, description='是否启用')


class CreateDictMajorParam(DictMajorSchemaBase):
    """创建专业目录参数"""

    pass


class UpdateDictMajorParam(SchemaBase):
    """更新专业目录参数"""

    name: str | None = Field(None, description='专业名称')
    aliases: list[str] | None = Field(None, description='专业别名列表')
    description: str | None = Field(None, description='专业说明')
    sort_order: int | None = Field(None, description='排序')
    is_active: bool | None = Field(None, description='是否启用')


class DictMajorParam(SchemaBase):
    """专业目录查询参数"""

    name: str | None = Field(None, description='专业名称')
    level: int | None = Field(None, description='级别')
    parent_code: str | None = Field(None, description='父级代码')
    edu_level: str | None = Field(None, description='学历层次')
    is_active: bool | None = Field(None, description='是否启用')


class GetDictMajorDetail(DictMajorSchemaBase):
    """专业目录详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetDictMajorTree(SchemaBase):
    """专业目录树形结构"""

    model_config = ConfigDict(from_attributes=True)

    code: str = Field(description='专业代码')
    name: str = Field(description='专业名称')
    level: int = Field(description='级别')
    edu_level: str = Field(description='学历层次')
    children: list['GetDictMajorTree'] = Field(default_factory=list, description='子专业')


class MajorMatchResult(SchemaBase):
    """专业匹配结果"""

    major_code: str = Field(description='专业代码')
    major_name: str = Field(description='专业名称')
    category_code: str | None = Field(None, description='专业类代码')
    category_name: str | None = Field(None, description='专业类名称')
    discipline_code: str | None = Field(None, description='学科门类代码')
    discipline_name: str | None = Field(None, description='学科门类名称')
    match_type: str = Field(description='匹配类型: exact/category/discipline/alias')
    match_score: int = Field(description='匹配分数: 100/85/70/80')
