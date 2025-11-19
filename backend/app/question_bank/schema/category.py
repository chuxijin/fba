#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class CategorySchemaBase(SchemaBase):
    """分类基础"""

    name: str = Field(description='分类名称')
    cat_type: int = Field(description='分类类型（0=全部 1=题库 2=词库 3=资料包 4=商城）')
    code: str = Field(description='分类编码')
    level: int = Field(default=1, description='分类层级')
    is_active: bool = Field(default=True, description='是否启用')
    sort_order: int = Field(default=0, description='排序权重')
    parent_id: int | None = Field(default=None, description='父级分类 ID')


class GetCategoryDetail(CategorySchemaBase):
    """分类详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='分类 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetCategoryTree(GetCategoryDetail):
    """分类树"""

    children: list['GetCategoryTree'] | None = Field(None, description='子分类')


class CategoryParam(SchemaBase):
    """分类参数"""

    cat_type: int | None = Field(None, description='分类类型')
    is_active: bool | None = Field(None, description='是否启用')


class CreateCategoryParam(CategorySchemaBase):
    """创建分类参数"""


class UpdateCategoryParam(CategorySchemaBase):
    """更新分类参数"""


class DeleteCategoryParam(SchemaBase):
    """删除分类参数"""

    ids: list[int] = Field(description='分类 ID 列表')
