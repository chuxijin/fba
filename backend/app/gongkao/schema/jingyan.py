#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date, datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class JingyanSchemaBase(SchemaBase):
    """经验基础"""

    title: str = Field(description='标题')
    category_id: int = Field(description='分类 ID')
    content: str = Field(description='内容')
    author: str | None = Field(None, description='作者')
    tags: str | None = Field(None, description='标签（逗号分隔）')
    daily_date: date | None = Field(None, description='发布日期')
    summary: str | None = Field(None, description='摘要')


class JingyanParam(SchemaBase):
    """经验查询参数"""

    title: str | None = Field(None, description='标题')
    category_id: int | None = Field(None, description='分类 ID')
    author: str | None = Field(None, description='作者')
    tags: str | None = Field(None, description='标签')
    daily_date: date | None = Field(None, description='发布日期')


class CreateJingyanParam(JingyanSchemaBase):
    """创建经验参数"""


class UpdateJingyanParam(SchemaBase):
    """更新经验参数"""

    title: str | None = Field(None, description='标题')
    category_id: int | None = Field(None, description='分类 ID')
    content: str | None = Field(None, description='内容')
    author: str | None = Field(None, description='作者')
    tags: str | None = Field(None, description='标签（逗号分隔）')
    daily_date: date | None = Field(None, description='发布日期')
    summary: str | None = Field(None, description='摘要')


class DeleteJingyanParam(SchemaBase):
    """删除经验参数"""

    ids: list[int] = Field(description='经验 ID 列表')


class GetJingyanDetail(JingyanSchemaBase):
    """经验详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='经验 ID')
    view_count: int = Field(description='阅读量')
    created_by: int = Field(description='创建者')
    updated_by: int | None = Field(None, description='修改者')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
