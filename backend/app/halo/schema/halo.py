#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pydantic import Field

from backend.common.schema import SchemaBase


class HaloPostItem(SchemaBase):
    """文章列表项"""

    name: str = Field(..., description='Halo 内部标识')
    title: str = Field(..., description='标题')
    slug: str = Field(..., description='别名')
    excerpt: str = Field('', description='摘要')
    cover: str = Field('', description='封面图')
    publish_time: str | None = Field(None, description='发布时间')
    categories: list[str] = Field(default_factory=list, description='分类名称列表')
    tags: list[str] = Field(default_factory=list, description='标签名称列表')
    view_count: int = Field(0, description='浏览量')


class HaloPostDetail(HaloPostItem):
    """文章详情"""

    content: str = Field('', description='HTML 内容')


class HaloCategoryItem(SchemaBase):
    """分类"""

    name: str = Field(..., description='Halo 内部标识')
    display_name: str = Field(..., description='显示名称')
    slug: str = Field(..., description='别名')
    post_count: int = Field(0, description='文章数量')


class HaloTagItem(SchemaBase):
    """标签"""

    name: str = Field(..., description='Halo 内部标识')
    display_name: str = Field(..., description='显示名称')
    slug: str = Field(..., description='别名')


class DocProjectItem(SchemaBase):
    """Docsme 项目"""

    name: str = Field(..., description='项目资源名称')
    display_name: str = Field('', description='项目显示名称')
    slug: str = Field('', description='项目别名')
    preferred_version_name: str = Field('', description='首选版本资源名称')


class DocProjectVersionItem(SchemaBase):
    """Docsme 项目版本"""

    name: str = Field(..., description='版本资源名称')
    project_name: str = Field('', description='项目资源名称')
    slug: str = Field('', description='版本别名')
    publish: bool = Field(False, description='是否发布')


class DocTreeNode(SchemaBase):
    """Docsme 文档树节点"""

    name: str = Field(..., description='节点 UUID')
    title: str = Field(..., description='标题')
    slug: str = Field(..., description='别名')
    type: str = Field(..., description='节点类型: TREE（目录）或 DOC（文档）')
    permalink: str = Field('', description='前端路径')
    doc_name: str = Field('', description='Doc 正文资源名称')
    project_version_name: str = Field('', description='项目版本资源名称')
    path: str = Field('', description='文档树路径')
    children: list['DocTreeNode'] = Field(default_factory=list, description='子节点')


class DocDetail(SchemaBase):
    """Docsme 文档详情（含 HTML 正文）"""

    name: str = Field(..., description='Doc UUID')
    doc_tree_name: str = Field('', description='DocTree 节点 UUID')
    doc_name: str = Field('', description='Doc 资源 UUID')
    title: str = Field(..., description='标题')
    permalink: str = Field('', description='前端路径')
    url: str = Field('', description='完整访问地址')
    content: str = Field('', description='HTML 正文')
    raw: str = Field('', description='原始正文')
    raw_type: str = Field('HTML', description='原始正文类型')
    updated_at: str | None = Field(None, description='最后更新时间')


class DocPreview(SchemaBase):
    """Docsme 文档预览页面"""

    name: str = Field(..., description='Doc UUID')
    title: str = Field(..., description='标题')
    url: str = Field('', description='发布页面地址')
    html: str = Field('', description='发布页面 HTML')
