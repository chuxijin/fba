#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field, model_validator

from backend.common.schema import SchemaBase


class _ShizhenBase(SchemaBase):
    """时政 schema 基类，负责从 Content ORM 抽取 extra 字段"""

    model_config = ConfigDict(from_attributes=True)

    @model_validator(mode='before')
    @classmethod
    def flatten_content(cls, data: Any) -> Any:
        """从 Content ORM 对象展平 extra 到顶层"""
        if not hasattr(data, 'extra'):
            return data
        extra = getattr(data, 'extra', None) or {}
        return {
            'id': data.id,
            'title': data.title,
            'summary': data.summary,
            'tags': data.tags,
            'original': getattr(data, 'content_html', None),
            'daily_date': extra.get('daily_date'),
            'origin_url': extra.get('origin_url'),
            'view_count': data.view_count,
            'publish_time': data.publish_time,
            'created_time': data.created_time,
            'updated_time': data.updated_time,
            'created_by': data.created_by,
            'updated_by': data.updated_by,
        }


class GetShizhenListDetail(_ShizhenBase):
    """时政列表项"""

    id: int
    title: str | None = Field(None, description='标题')
    summary: str | None = Field(None, description='摘要')
    tags: list[str] | None = Field(None, description='标签')
    daily_date: str | None = Field(None, description='日期')
    origin_url: str | None = Field(None, description='来源链接')
    view_count: int = Field(0, description='浏览量')
    publish_time: datetime | None = Field(None, description='发布时间')
    created_time: datetime
    updated_time: datetime | None = None


class GetShizhenDetail(_ShizhenBase):
    """时政详情"""

    id: int
    title: str | None = Field(None, description='标题')
    summary: str | None = Field(None, description='摘要')
    original: str | None = Field(None, description='原文 HTML')
    tags: list[str] | None = Field(None, description='标签')
    daily_date: str | None = Field(None, description='日期')
    origin_url: str | None = Field(None, description='来源链接')
    view_count: int = Field(0, description='浏览量')
    publish_time: datetime | None = Field(None, description='发布时间')
    created_time: datetime
    updated_time: datetime | None = None
    created_by: int | None = None
    updated_by: int | None = None
