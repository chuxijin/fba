#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class CategorySchemaBase(SchemaBase):
    """分类基础"""

    parent_id: int | None = Field(None, description='父级分类 ID')
    name: str = Field(description='分类名称')
    icon: str | None = Field(None, description='分类图标')
    color: str | None = Field(None, description='分类颜色')
    sort_order: int = Field(0, ge=0, description='排序顺序')


class CreateCategoryParam(CategorySchemaBase):
    """创建分类参数"""


class UpdateCategoryParam(SchemaBase):
    """更新分类参数"""

    parent_id: int | None = Field(None, description='父级分类 ID')
    name: str | None = Field(None, description='分类名称')
    icon: str | None = Field(None, description='分类图标')
    color: str | None = Field(None, description='分类颜色')
    sort_order: int | None = Field(None, ge=0, description='排序顺序')


class DeleteCategoryParam(SchemaBase):
    """删除分类参数"""

    pks: list[int] = Field(description='分类 ID 列表')


class GetCategoryDetail(CategorySchemaBase):
    """分类详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='分类 ID')
    server_id: str | None = Field(None, description='服务器 ID')
    parent_server_id: str | None = Field(None, description='父级分类服务器 ID')
    sync_status: str = Field(description='同步状态')
    last_synced_at: int | None = Field(None, description='最后同步时间戳')
    version: int = Field(description='版本号')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
    created_by: int = Field(description='创建者')
    updated_by: int | None = Field(None, description='更新者')
    deleted_at: int | None = Field(None, description='软删除时间戳')

