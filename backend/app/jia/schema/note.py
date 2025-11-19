#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class NoteSchemaBase(SchemaBase):
    """笔记基础"""

    type: str = Field(description='类型: folder 或 note')
    parent_id: int | None = Field(None, description='父级 ID')
    category_ids: str | None = Field(None, description='分类ID列表(JSON 数组)')
    tag_ids: str | None = Field(None, description='标签ID列表(JSON 数组)')
    name: str = Field(description='名称')
    title: str | None = Field(None, description='笔记标题')
    content: str | None = Field(None, description='内容(Delta JSON 格式)')
    icon: str | None = Field(None, description='图标')
    color: str | None = Field(None, description='颜色标记')
    sort_order: int = Field(0, ge=0, description='排序顺序')
    is_pinned: int = Field(0, description='是否置顶(0/1)')
    is_favorite: int = Field(0, description='是否收藏(0/1)')


class CreateNoteParam(NoteSchemaBase):
    """创建笔记参数"""


class UpdateNoteParam(SchemaBase):
    """更新笔记参数"""

    parent_id: int | None = Field(None, description='父级 ID')
    category_ids: str | None = Field(None, description='分类ID列表(JSON 数组)')
    tag_ids: str | None = Field(None, description='标签ID列表(JSON 数组)')
    name: str | None = Field(None, description='名称')
    title: str | None = Field(None, description='笔记标题')
    content: str | None = Field(None, description='内容(Delta JSON 格式)')
    icon: str | None = Field(None, description='图标')
    color: str | None = Field(None, description='颜色标记')
    sort_order: int | None = Field(None, ge=0, description='排序顺序')
    is_pinned: int | None = Field(None, description='是否置顶(0/1)')
    is_favorite: int | None = Field(None, description='是否收藏(0/1)')


class DeleteNoteParam(SchemaBase):
    """删除笔记参数"""

    pks: list[int] = Field(description='笔记 ID 列表')


class GetNoteDetail(NoteSchemaBase):
    """笔记详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='笔记 ID')
    server_id: str | None = Field(None, description='服务器上的 ID')
    parent_server_id: str | None = Field(None, description='父级服务器 ID')
    word_count: int = Field(description='字数统计')
    sync_status: str = Field(description='同步状态')
    last_synced_at: int | None = Field(None, description='最后同步时间戳')
    version: int = Field(description='版本号')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
    created_by: int = Field(description='创建者')
    updated_by: int | None = Field(None, description='更新者')
    deleted_at: int | None = Field(None, description='软删除时间戳')
