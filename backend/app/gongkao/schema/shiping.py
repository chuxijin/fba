#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date, datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class ShipingSchemaBase(SchemaBase):
    """时评基础"""

    title: str = Field(description='标题')
    source: str | None = Field(None, description='来源')
    author: str | None = Field(None, description='作者')
    keywords: str | None = Field(None, description='关键词')
    daily_date: date | None = Field(None, description='每日时间')
    content: str | None = Field(None, description='内容')
    sidebar: str | None = Field(None, description='右边栏内容')
    mind_map: str | None = Field(None, description='思维导图')


class ShipingParam(SchemaBase):
    """时评查询参数"""

    title: str | None = Field(None, description='标题')
    source: str | None = Field(None, description='来源')
    author: str | None = Field(None, description='作者')
    keywords: str | None = Field(None, description='关键词')
    daily_date: date | None = Field(None, description='每日时间')


class CreateShipingParam(ShipingSchemaBase):
    """创建时评参数"""


class UpdateShipingParam(SchemaBase):
    """更新时评参数"""

    title: str | None = Field(None, description='标题')
    source: str | None = Field(None, description='来源')
    author: str | None = Field(None, description='作者')
    keywords: str | None = Field(None, description='关键词')
    daily_date: date | None = Field(None, description='每日时间')
    content: str | None = Field(None, description='内容')
    sidebar: str | None = Field(None, description='右边栏内容')
    mind_map: str | None = Field(None, description='思维导图')


class DeleteShipingParam(SchemaBase):
    """删除时评参数"""

    ids: list[int] = Field(description='时评 ID 列表')


class GetShipingDetail(ShipingSchemaBase):
    """时评详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='时评 ID')
    view_count: int = Field(description='阅读量')
    created_by: int = Field(description='创建者')
    updated_by: int | None = Field(None, description='修改者')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
