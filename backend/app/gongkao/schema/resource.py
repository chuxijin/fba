#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""资料 Schema"""

from datetime import datetime

from pydantic import Field

from backend.common.schema import SchemaBase


class ResourceBase(SchemaBase):
    """资料基础"""

    title: str = Field(description='标题')
    description: str | None = Field(None, description='描述')
    category_id: int = Field(description='分类ID')
    file_path: str | None = Field(None, description='本地文件路径')
    link: str | None = Field(None, description='外部链接')
    file_type: str | None = Field(None, description='文件类型：pdf/doc/video/link')
    sort_order: int = Field(0, description='排序')
    status: bool = Field(True, description='状态')


class CreateResourceParam(ResourceBase):
    """创建资料"""

    pass


class UpdateResourceParam(SchemaBase):
    """更新资料"""

    title: str | None = Field(None, description='标题')
    description: str | None = Field(None, description='描述')
    category_id: int | None = Field(None, description='分类ID')
    file_path: str | None = Field(None, description='本地文件路径')
    link: str | None = Field(None, description='外部链接')
    file_type: str | None = Field(None, description='文件类型')
    sort_order: int | None = Field(None, description='排序')
    status: bool | None = Field(None, description='状态')


class GetResourceDetail(ResourceBase):
    """资料详情"""

    id: int = Field(description='ID')
    view_count: int = Field(0, description='查看次数')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')

    class Config:
        from_attributes = True


class GetResourceListParams(SchemaBase):
    """资料列表查询参数"""

    title: str | None = Field(None, description='标题')
    category_id: int | list[int] | None = Field(None, description='分类ID')
    file_type: str | None = Field(None, description='文件类型')
    status: bool | None = Field(None, description='状态')
