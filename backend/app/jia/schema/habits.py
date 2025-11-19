#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class HabitSchemaBase(SchemaBase):
    """习惯基础"""

    name: str = Field(description='习惯名称')
    description: str | None = Field(None, description='习惯简短描述')
    content: str | None = Field(None, description='习惯详细内容(Delta JSON 格式)')
    icon: str | None = Field(None, description='图标')
    color: str | None = Field(None, description='颜色标记')
    category_ids: str | None = Field(None, description='分类ID列表(JSON 数组)')
    tag_ids: str | None = Field(None, description='标签ID列表(JSON 数组)')
    difficulty: int = Field(1, ge=1, le=3, description='难度等级(1-简单/2-中等/3-困难)')
    motivation: str | None = Field(None, description='动力/原因描述')
    reward: str | None = Field(None, description='奖励描述')
    target_type: str | None = Field(None, description='目标类型: daily/weekly/monthly')
    target_value: int | None = Field(None, description='目标值')
    start_date: int | None = Field(None, description='习惯开始日期时间戳')
    end_date: int | None = Field(None, description='习惯预计结束日期')
    duration_days: int | None = Field(None, description='习惯持续天数')
    reminder_enabled: int = Field(1, description='是否启用提醒(0/1)')
    reminder_time: str | None = Field(None, description='提醒时间(HH:mm)')
    reminder_days: str | None = Field(None, description='提醒日期(JSON 数组)')
    attachments: str | None = Field(None, description='附件元数据(JSON 格式)')
    is_archived: int = Field(0, description='是否归档(0/1)')
    is_pinned: int = Field(0, description='是否置顶(0/1)')


class CreateHabitParam(HabitSchemaBase):
    """创建习惯参数"""


class UpdateHabitParam(SchemaBase):
    """更新习惯参数"""

    name: str | None = Field(None, description='习惯名称')
    description: str | None = Field(None, description='习惯简短描述')
    content: str | None = Field(None, description='习惯详细内容(Delta JSON 格式)')
    icon: str | None = Field(None, description='图标')
    color: str | None = Field(None, description='颜色标记')
    category_ids: str | None = Field(None, description='分类ID列表(JSON 数组)')
    tag_ids: str | None = Field(None, description='标签ID列表(JSON 数组)')
    difficulty: int | None = Field(None, ge=1, le=3, description='难度等级(1-简单/2-中等/3-困难)')
    motivation: str | None = Field(None, description='动力/原因描述')
    reward: str | None = Field(None, description='奖励描述')
    target_type: str | None = Field(None, description='目标类型: daily/weekly/monthly')
    target_value: int | None = Field(None, description='目标值')
    start_date: int | None = Field(None, description='习惯开始日期时间戳')
    end_date: int | None = Field(None, description='习惯预计结束日期')
    duration_days: int | None = Field(None, description='习惯持续天数')
    reminder_enabled: int | None = Field(None, description='是否启用提醒(0/1)')
    reminder_time: str | None = Field(None, description='提醒时间(HH:mm)')
    reminder_days: str | None = Field(None, description='提醒日期(JSON 数组)')
    attachments: str | None = Field(None, description='附件元数据(JSON 格式)')
    is_archived: int | None = Field(None, description='是否归档(0/1)')
    is_pinned: int | None = Field(None, description='是否置顶(0/1)')


class DeleteHabitParam(SchemaBase):
    """删除习惯参数"""

    pks: list[int] = Field(description='习惯 ID 列表')


class GetHabitDetail(HabitSchemaBase):
    """习惯详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='习惯 ID')
    server_id: str | None = Field(None, description='服务器ID')
    image_count: int = Field(description='图片数量统计')
    video_count: int = Field(description='视频数量统计')
    audio_count: int = Field(description='音频数量统计')
    current_streak: int = Field(description='当前连续天数')
    longest_streak: int = Field(description='最长连续天数')
    total_completed: int = Field(description='总完成次数')
    success_rate: float = Field(description='成功率(0.0-1.0)')
    last_checkin_date: int | None = Field(None, description='最后打卡日期')
    sync_status: str = Field(description='同步状态')
    version: int = Field(description='版本号')
    last_synced_at: int | None = Field(None, description='最后同步时间戳')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
    created_by: int = Field(description='创建者')
    updated_by: int | None = Field(None, description='更新者')
    deleted_at: int | None = Field(None, description='软删除时间戳')


class HabitRecordSchemaBase(SchemaBase):
    """习惯打卡记录基础"""

    habit_id: int = Field(description='习惯 ID')
    date: int = Field(description='打卡日期时间戳')
    checkin_time: int | None = Field(None, description='打卡时间戳')
    count: int = Field(1, description='当天完成次数')
    completion_percentage: float | None = Field(None, ge=0.0, le=1.0, description='完成百分比(0.0-1.0)')
    note: str | None = Field(None, description='备注')
    mood: str | None = Field(None, description='打卡时的心情')
    location: str | None = Field(None, description='打卡位置')
    attachments: str | None = Field(None, description='附件元数据(JSON 格式)')
    checkin_type: str = Field('manual', description='打卡类型: manual/auto/reminder')
    status: str = Field('completed', description='状态: completed/partial/failed')


class CreateHabitRecordParam(HabitRecordSchemaBase):
    """创建习惯打卡记录参数"""


class UpdateHabitRecordParam(SchemaBase):
    """更新习惯打卡记录参数"""

    date: int | None = Field(None, description='打卡日期时间戳')
    checkin_time: int | None = Field(None, description='打卡时间戳')
    count: int | None = Field(None, description='当天完成次数')
    completion_percentage: float | None = Field(None, ge=0.0, le=1.0, description='完成百分比(0.0-1.0)')
    note: str | None = Field(None, description='备注')
    mood: str | None = Field(None, description='打卡时的心情')
    location: str | None = Field(None, description='打卡位置')
    attachments: str | None = Field(None, description='附件元数据(JSON 格式)')
    checkin_type: str | None = Field(None, description='打卡类型: manual/auto/reminder')
    status: str | None = Field(None, description='状态: completed/partial/failed')


class DeleteHabitRecordParam(SchemaBase):
    """删除习惯打卡记录参数"""

    pks: list[int] = Field(description='打卡记录 ID 列表')


class GetHabitRecordDetail(HabitRecordSchemaBase):
    """习惯打卡记录详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='记录 ID')
    server_id: str | None = Field(None, description='服务器ID')
    habit_server_id: str | None = Field(None, description='习惯服务器ID')
    image_count: int = Field(description='图片数量统计')
    sync_status: str = Field(description='同步状态')
    version: int = Field(description='版本号')
    last_synced_at: int | None = Field(None, description='最后同步时间戳')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
    created_by: int = Field(description='创建者')
    updated_by: int | None = Field(None, description='更新者')
    deleted_at: int | None = Field(None, description='软删除时间戳')

