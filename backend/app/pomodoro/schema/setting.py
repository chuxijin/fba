#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class PomodoroUserSettingSchemaBase(SchemaBase):
    """番茄用户设置基础模型"""

    focus_minutes: int = Field(25, ge=1, le=240, description='默认专注分钟数')
    short_break_minutes: int = Field(5, ge=1, le=60, description='短休息分钟数')
    long_break_minutes: int = Field(15, ge=1, le=120, description='长休息分钟数')
    long_break_interval: int = Field(4, ge=1, le=20, description='长休息间隔番茄数')
    daily_focus_minutes: int = Field(120, ge=0, le=1440, description='每日专注目标分钟数')
    weekly_focus_minutes: int = Field(600, ge=0, le=10080, description='每周专注目标分钟数')
    auto_start_break: bool = Field(False, description='是否自动开始休息')
    auto_start_next_focus: bool = Field(False, description='是否自动开始下一轮专注')
    sound_enabled: bool = Field(False, description='是否开启背景音')
    background_sound: str | None = Field(None, max_length=50, description='背景音')


class CreatePomodoroUserSettingInternal(PomodoroUserSettingSchemaBase):
    """创建番茄用户设置内部参数"""

    user_id: int = Field(description='用户 ID')


class UpdatePomodoroUserSettingParam(SchemaBase):
    """更新番茄用户设置参数"""

    focus_minutes: int | None = Field(None, ge=1, le=240, description='默认专注分钟数')
    short_break_minutes: int | None = Field(None, ge=1, le=60, description='短休息分钟数')
    long_break_minutes: int | None = Field(None, ge=1, le=120, description='长休息分钟数')
    long_break_interval: int | None = Field(None, ge=1, le=20, description='长休息间隔番茄数')
    daily_focus_minutes: int | None = Field(None, ge=0, le=1440, description='每日专注目标分钟数')
    weekly_focus_minutes: int | None = Field(None, ge=0, le=10080, description='每周专注目标分钟数')
    auto_start_break: bool | None = Field(None, description='是否自动开始休息')
    auto_start_next_focus: bool | None = Field(None, description='是否自动开始下一轮专注')
    sound_enabled: bool | None = Field(None, description='是否开启背景音')
    background_sound: str | None = Field(None, max_length=50, description='背景音')


class GetPomodoroUserSettingDetail(PomodoroUserSettingSchemaBase):
    """番茄用户设置详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='设置 ID')
    user_id: int = Field(description='用户 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
