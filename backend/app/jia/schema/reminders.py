#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class ReminderSchemaBase(SchemaBase):
    """提醒基础"""

    category_ids: str | None = Field(None, description='分类ID列表(JSON 数组)')
    tag_ids: str | None = Field(None, description='标签ID列表(JSON 数组)')
    title: str = Field(description='标题')
    description: str | None = Field(None, description='描述')
    content: str | None = Field(None, description='内容(Delta JSON 格式)')
    scheduled_time: int = Field(description='计划时间时间戳')
    repeat_type: str | None = Field(None, description='重复类型')
    repeat_config: str | None = Field(None, description='重复配置(JSON)')
    reminder_method: str = Field('notification', description='提醒方式: notification/email/sms')
    reminder_before_minutes: str | None = Field(None, description='提前提醒分钟数(JSON 数组)')
    attachments: str | None = Field(None, description='附件元数据(JSON 格式)')
    is_important: int = Field(0, description='是否重要(0/1)')
    is_starred: int = Field(0, description='是否星标(0/1)')
    is_pinned: int = Field(0, description='是否置顶(0/1)')
    priority: int = Field(0, ge=0, le=2, description='优先级(0-普通/1-重要/2-紧急)')
    location: str | None = Field(None, description='位置')
    related_note_ids: str | None = Field(None, description='关联笔记ID列表(JSON 数组)')
    related_diary_ids: str | None = Field(None, description='关联日记ID列表(JSON 数组)')
    related_habit_ids: str | None = Field(None, description='关联习惯ID列表(JSON 数组)')


class CreateReminderParam(ReminderSchemaBase):
    """创建提醒参数"""


class UpdateReminderParam(SchemaBase):
    """更新提醒参数"""

    category_ids: str | None = Field(None, description='分类ID列表(JSON 数组)')
    tag_ids: str | None = Field(None, description='标签ID列表(JSON 数组)')
    title: str | None = Field(None, description='标题')
    description: str | None = Field(None, description='描述')
    content: str | None = Field(None, description='内容(Delta JSON 格式)')
    scheduled_time: int | None = Field(None, description='计划时间时间戳')
    repeat_type: str | None = Field(None, description='重复类型')
    repeat_config: str | None = Field(None, description='重复配置(JSON)')
    reminder_method: str | None = Field(None, description='提醒方式: notification/email/sms')
    reminder_before_minutes: str | None = Field(None, description='提前提醒分钟数(JSON 数组)')
    attachments: str | None = Field(None, description='附件元数据(JSON 格式)')
    is_completed: int | None = Field(None, description='是否完成(0/1)')
    is_important: int | None = Field(None, description='是否重要(0/1)')
    is_starred: int | None = Field(None, description='是否星标(0/1)')
    is_pinned: int | None = Field(None, description='是否置顶(0/1)')
    priority: int | None = Field(None, ge=0, le=2, description='优先级(0-普通/1-重要/2-紧急)')
    location: str | None = Field(None, description='位置')
    related_note_ids: str | None = Field(None, description='关联笔记ID列表(JSON 数组)')
    related_diary_ids: str | None = Field(None, description='关联日记ID列表(JSON 数组)')
    related_habit_ids: str | None = Field(None, description='关联习惯ID列表(JSON 数组)')


class DeleteReminderParam(SchemaBase):
    """删除提醒参数"""

    pks: list[int] = Field(description='提醒 ID 列表')


class GetReminderDetail(ReminderSchemaBase):
    """提醒详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='提醒 ID')
    server_id: str | None = Field(None, description='服务器ID')
    image_count: int = Field(description='图片数量统计')
    video_count: int = Field(description='视频数量统计')
    audio_count: int = Field(description='音频数量统计')
    is_completed: int = Field(description='是否完成(0/1)')
    completed_at: int | None = Field(None, description='完成时间戳')
    completion_rate: float = Field(description='完成率(0.0-1.0)')
    total_occurrences: int = Field(description='总发生次数')
    completed_occurrences: int = Field(description='已完成次数')
    last_triggered_at: int | None = Field(None, description='最后触发时间戳')
    next_trigger_time: int | None = Field(None, description='下次触发时间')
    sync_status: str = Field(description='同步状态')
    version: int = Field(description='版本号')
    last_synced_at: int | None = Field(None, description='最后同步时间戳')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
    created_by: int = Field(description='创建者')
    updated_by: int | None = Field(None, description='更新者')
    deleted_at: int | None = Field(None, description='软删除时间戳')

