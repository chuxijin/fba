#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class CategorySchemaBase(SchemaBase):
    """分类基础"""

    app_code: str = Field(description='应用标识')
    type: str = Field(default='default', description='分类类型')
    name: str = Field(description='分类名称')
    code: str | None = Field(None, description='分类编码')
    description: str | None = Field(None, description='分类描述')
    parent_id: int | None = Field(None, description='父级分类 ID')
    icon: str | None = Field(None, description='图标')
    color: str | None = Field(None, description='颜色')
    sort_order: int = Field(default=0, description='排序权重')
    status: bool = Field(default=True, description='状态')
    is_system: bool = Field(default=False, description='是否系统分类')
    remark: str | None = Field(None, description='备注')
    extra_data: dict | None = Field(None, description='扩展数据')


class CreateCategoryParam(CategorySchemaBase):
    """创建分类参数"""


class UpdateCategoryParam(SchemaBase):
    """更新分类参数"""

    name: str | None = Field(None, description='分类名称')
    code: str | None = Field(None, description='分类编码')
    description: str | None = Field(None, description='分类描述')
    parent_id: int | None = Field(None, description='父级分类 ID')
    icon: str | None = Field(None, description='图标')
    color: str | None = Field(None, description='颜色')
    sort_order: int | None = Field(None, description='排序权重')
    status: bool | None = Field(None, description='状态')
    is_system: bool | None = Field(None, description='是否系统分类')
    remark: str | None = Field(None, description='备注')
    extra_data: dict | None = Field(None, description='扩展数据')


class DeleteCategoryParam(SchemaBase):
    """删除分类参数"""

    ids: list[int] = Field(description='分类 ID 列表')


class GetCategoryDetail(CategorySchemaBase):
    """分类详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='分类 ID')
    level: int = Field(description='层级')
    path: str | None = Field(None, description='物化路径')
    created_by: int | None = Field(None, description='创建者')
    updated_by: int | None = Field(None, description='修改者')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetCategoryTree(GetCategoryDetail):
    """分类树"""

    children: list['GetCategoryTree'] | None = Field(None, description='子分类')


class CategoryDocBindingParam(SchemaBase):
    """分类文档关联参数"""

    halo_project_name: str = Field(min_length=1, max_length=64, description='Docsme 项目资源名称')
    halo_project_version_name: str = Field(min_length=1, max_length=64, description='Docsme 项目版本资源名称')
    halo_tree_name: str = Field(min_length=1, max_length=64, description='DocTree 节点资源名称')
    halo_doc_name: str = Field(min_length=1, max_length=64, description='Doc 正文资源名称')
    title: str = Field(min_length=1, max_length=255, description='文档标题')
    relation_type: str = Field(default='teaching', min_length=1, max_length=32, description='关联类型')
    halo_doc_path: str | None = Field(None, max_length=255, description='Docsme 文档路径')
    halo_permalink: str | None = Field(None, max_length=512, description='Docsme 访问路径')
    enabled: bool = Field(default=True, description='是否启用')
    sort_order: int = Field(default=0, ge=0, description='排序')
    extra_data: dict | None = Field(None, description='扩展数据')


class CreateCategoryDocBindingParam(CategoryDocBindingParam):
    """创建分类文档关联参数"""


class UpdateCategoryDocBindingParam(SchemaBase):
    """更新分类文档关联参数"""

    halo_project_name: str | None = Field(None, min_length=1, max_length=64, description='Docsme 项目资源名称')
    halo_project_version_name: str | None = Field(
        None,
        min_length=1,
        max_length=64,
        description='Docsme 项目版本资源名称',
    )
    halo_tree_name: str | None = Field(None, min_length=1, max_length=64, description='DocTree 节点资源名称')
    halo_doc_name: str | None = Field(None, min_length=1, max_length=64, description='Doc 正文资源名称')
    title: str | None = Field(None, min_length=1, max_length=255, description='文档标题')
    relation_type: str | None = Field(None, min_length=1, max_length=32, description='关联类型')
    halo_doc_path: str | None = Field(None, max_length=255, description='Docsme 文档路径')
    halo_permalink: str | None = Field(None, max_length=512, description='Docsme 访问路径')
    enabled: bool | None = Field(None, description='是否启用')
    sort_order: int | None = Field(None, ge=0, description='排序')
    extra_data: dict | None = Field(None, description='扩展数据')


class GetCategoryDocBindingDetail(CategoryDocBindingParam):
    """分类文档关联详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='关联 ID')
    category_id: int = Field(description='系统分类 ID')
    category_code: str | None = Field(None, description='分类编码快照')
    category_path: str | None = Field(None, description='分类路径快照')
    created_by: int | None = Field(None, description='创建者')
    updated_by: int | None = Field(None, description='修改者')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
