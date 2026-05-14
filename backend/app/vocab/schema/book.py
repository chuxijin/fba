#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class CreateBookParam(SchemaBase):
    """创建词书参数"""

    name: str = Field(min_length=1, max_length=100, description='词书名称')
    description: str | None = Field(None, max_length=500, description='词书描述')
    cover_image: str | None = Field(None, max_length=255, description='封面图 URL')
    category: str = Field(default='custom', max_length=50, description='分类')
    is_official: bool = Field(default=False, description='是否官方预置')
    sort_order: int = Field(default=0, description='排序')
    status: int = Field(default=1, ge=0, le=1, description='状态(0 下架 1 上架)')


class UpdateBookParam(SchemaBase):
    """更新词书参数"""

    name: str | None = Field(None, max_length=100, description='词书名称')
    description: str | None = Field(None, max_length=500, description='词书描述')
    cover_image: str | None = Field(None, max_length=255, description='封面图 URL')
    category: str | None = Field(None, max_length=50, description='分类')
    is_official: bool | None = Field(None, description='是否官方预置')
    sort_order: int | None = Field(None, description='排序')
    status: int | None = Field(None, ge=0, le=1, description='状态')


class GetBookDetail(SchemaBase):
    """词书详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='词书 ID')
    name: str = Field(description='词书名称')
    description: str | None = Field(None, description='词书描述')
    cover_image: str | None = Field(None, description='封面图 URL')
    category: str = Field(description='分类')
    word_count: int = Field(description='词汇总数')
    is_official: bool = Field(description='是否官方预置')
    creator_id: int | None = Field(None, description='创建者用户 ID')
    sort_order: int = Field(description='排序')
    status: int = Field(description='状态')
    created_by: int = Field(description='创建者')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetBookListItem(SchemaBase):
    """词书列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='词书 ID')
    name: str = Field(description='词书名称')
    description: str | None = Field(None, description='词书描述')
    cover_image: str | None = Field(None, description='封面图 URL')
    category: str = Field(description='分类')
    word_count: int = Field(description='词汇总数')
    is_official: bool = Field(description='是否官方预置')
    status: int = Field(description='状态')


class BatchAddWordsParam(SchemaBase):
    """批量添加单词到词书参数"""

    word_ids: list[int] = Field(min_length=1, description='单词 ID 列表')


class BatchRemoveWordsParam(SchemaBase):
    """批量从词书移除单词参数"""

    word_ids: list[int] = Field(min_length=1, description='单词 ID 列表')


class CreateBookWordParam(SchemaBase):
    """词书单词关联参数"""

    book_id: int = Field(description='词书 ID')
    word_id: int = Field(description='单词 ID')
    sort_order: int = Field(default=0, description='在词书中的顺序')
