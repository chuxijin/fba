#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class BiliCategorySchemaBase(SchemaBase):
    """B 站分类基础模型"""

    name: str = Field(description='分类名称')
    description: str | None = Field(None, description='分类描述')
    sort: int = Field(0, description='排序')
    status: int = Field(1, description='状态(0 停用 1 正常)')
    parent_id: int | None = Field(None, description='父分类 ID')


class CreateBiliCategoryParam(BiliCategorySchemaBase):
    """创建 B 站分类参数"""


class UpdateBiliCategoryParam(SchemaBase):
    """更新 B 站分类参数"""

    name: str | None = Field(None, description='分类名称')
    description: str | None = Field(None, description='分类描述')
    sort: int | None = Field(None, description='排序')
    status: int | None = Field(None, description='状态(0 停用 1 正常)')
    parent_id: int | None = Field(None, description='父分类 ID')


class GetBiliCategoryDetail(BiliCategorySchemaBase):
    """B 站分类详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetBiliCategoryTree(GetBiliCategoryDetail):
    """B 站分类树"""

    children: list['GetBiliCategoryTree'] | None = Field(None, description='子分类')
