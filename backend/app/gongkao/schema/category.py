#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class CategorySchemaBase(SchemaBase):
    """分类基础"""

    name: str = Field(description='分类名称')
    type: str = Field(description='分类类型')
    parent_id: int | None = Field(None, description='父级分类 ID')
    description: str | None = Field(None, description='分类描述')
    icon: str | None = Field(None, description='图标')
    color: str | None = Field(None, description='颜色标识')
    sort_order: int = Field(0, description='排序权重')
    status: bool = Field(True, description='状态')


class CategoryParam(SchemaBase):
    """分类查询参数"""

    name: str | None = Field(None, description='分类名称')
    type: str | None = Field(None, description='分类类型')
    parent_id: int | None = Field(None, description='父级分类 ID')
    status: bool | None = Field(None, description='状态')


class CreateCategoryParam(CategorySchemaBase):
    """创建分类参数"""


class UpdateCategoryParam(SchemaBase):
    """更新分类参数"""

    name: str | None = Field(None, description='分类名称')
    type: str | None = Field(None, description='分类类型')
    parent_id: int | None = Field(None, description='父级分类 ID')
    description: str | None = Field(None, description='分类描述')
    icon: str | None = Field(None, description='图标')
    color: str | None = Field(None, description='颜色标识')
    sort_order: int | None = Field(None, description='排序权重')
    status: bool | None = Field(None, description='状态')


class DeleteCategoryParam(SchemaBase):
    """删除分类参数"""

    ids: list[int] = Field(description='分类 ID 列表')


class GetCategoryDetail(CategorySchemaBase):
    """分类详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='分类 ID')
    created_by: int = Field(description='创建者')
    updated_by: int | None = Field(None, description='修改者')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
