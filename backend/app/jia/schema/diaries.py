#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class DiarySchemaBase(SchemaBase):
    """日记基础"""

    date: int = Field(description='日记日期时间戳')
    category_ids: str | None = Field(None, description='分类ID列表(JSON 数组)')
    tag_ids: str | None = Field(None, description='标签ID列表(JSON 数组)')
    title: str | None = Field(None, description='标题')
    content: str = Field(description='内容(Delta JSON 格式)')
    summary: str | None = Field(None, description='日记摘要/总结')
    mood: str | None = Field(None, description='主要心情')
    mood_tags: str | None = Field(None, description='多个心情标签(JSON 数组)')
    mood_intensity: int | None = Field(None, ge=1, le=5, description='心情强度(1-5)')
    weather: str | None = Field(None, description='天气')
    location: str | None = Field(None, description='位置')
    attachments: str | None = Field(None, description='附件元数据(JSON 格式)')
    is_starred: int = Field(0, description='是否星标/重要(0/1)')
    is_pinned: int = Field(0, description='是否置顶(0/1)')
    is_encrypted: int = Field(0, description='是否加密(0/1)')
    priority: int = Field(0, ge=0, le=2, description='优先级(0-普通/1-重要/2-非常重要)')


class CreateDiaryParam(DiarySchemaBase):
    """创建日记参数"""


class UpdateDiaryParam(SchemaBase):
    """更新日记参数"""

    date: int | None = Field(None, description='日记日期时间戳')
    category_ids: str | None = Field(None, description='分类ID列表(JSON 数组)')
    tag_ids: str | None = Field(None, description='标签ID列表(JSON 数组)')
    title: str | None = Field(None, description='标题')
    content: str | None = Field(None, description='内容(Delta JSON 格式)')
    summary: str | None = Field(None, description='日记摘要/总结')
    mood: str | None = Field(None, description='主要心情')
    mood_tags: str | None = Field(None, description='多个心情标签(JSON 数组)')
    mood_intensity: int | None = Field(None, ge=1, le=5, description='心情强度(1-5)')
    weather: str | None = Field(None, description='天气')
    location: str | None = Field(None, description='位置')
    attachments: str | None = Field(None, description='附件元数据(JSON 格式)')
    is_starred: int | None = Field(None, description='是否星标/重要(0/1)')
    is_pinned: int | None = Field(None, description='是否置顶(0/1)')
    is_encrypted: int | None = Field(None, description='是否加密(0/1)')
    priority: int | None = Field(None, ge=0, le=2, description='优先级(0-普通/1-重要/2-非常重要)')


class DeleteDiaryParam(SchemaBase):
    """删除日记参数"""

    pks: list[int] = Field(description='日记 ID 列表')


class GetDiaryDetail(DiarySchemaBase):
    """日记详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='日记 ID')
    server_id: str | None = Field(None, description='服务器ID')
    word_count: int = Field(description='字数统计')
    image_count: int = Field(description='图片数量统计')
    video_count: int = Field(description='视频数量统计')
    audio_count: int = Field(description='音频数量统计')
    sync_status: str = Field(description='同步状态')
    version: int = Field(description='版本号')
    last_synced_at: int | None = Field(None, description='最后同步时间戳')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
    created_by: int = Field(description='创建者')
    updated_by: int | None = Field(None, description='更新者')
    deleted_at: int | None = Field(None, description='软删除时间戳')

