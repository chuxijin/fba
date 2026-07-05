#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date, datetime

from pydantic import ConfigDict, Field

from backend.app.admin.schema.tag import GetSysTagTargetWithTag
from backend.app.admin.schema.cat import GetSysCatTargetWithCat
from backend.app.pomodoro.enums import PomodoroHabitStatus
from backend.common.schema import SchemaBase


class PomodoroHabitSchemaBase(SchemaBase):
    """番茄习惯基础模型"""

    name: str = Field(description='习惯名称', min_length=1, max_length=100)
    target_count: int = Field(1, ge=1, le=100, description='每日目标次数')
    repeat_days: str | None = Field(None, description='自定义重复星期，逗号分隔，0=周一...6=周日')


class CreatePomodoroHabitParam(PomodoroHabitSchemaBase):
    """创建番茄习惯参数"""


class CreatePomodoroHabitInternal(PomodoroHabitSchemaBase):
    """创建番茄习惯内部参数"""

    user_id: int = Field(description='用户 ID')
    status: PomodoroHabitStatus = Field(PomodoroHabitStatus.enabled, description='习惯状态')


class UpdatePomodoroHabitParam(SchemaBase):
    """更新番茄习惯参数"""

    name: str | None = Field(None, min_length=1, max_length=100, description='习惯名称')
    target_count: int | None = Field(None, ge=1, le=100, description='每日目标次数')
    repeat_days: str | None = Field(None, description='自定义重复星期，逗号分隔，0=周一...6=周日')
    status: PomodoroHabitStatus | None = Field(None, description='习惯状态')


class CheckinPomodoroHabitParam(SchemaBase):
    """番茄习惯打卡参数"""

    checkin_date: date | None = Field(None, description='打卡日期')
    count: int = Field(1, ge=1, le=100, description='打卡次数')


class CreatePomodoroHabitCheckinInternal(SchemaBase):
    """创建番茄习惯打卡内部参数"""

    user_id: int = Field(description='用户 ID')
    habit_id: int = Field(description='习惯 ID')
    checkin_date: date = Field(description='打卡日期')
    checked_at: datetime = Field(description='最近打卡时间')
    count: int = Field(1, ge=1, description='打卡次数')


class GetPomodoroHabitDetail(PomodoroHabitSchemaBase):
    """番茄习惯详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='习惯 ID')
    user_id: int = Field(description='用户 ID')
    status: PomodoroHabitStatus = Field(description='习惯状态')
    repeat_days: str | None = Field(None, description='自定义重复星期，逗号分隔，0=周一...6=周日')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
    tags: list[GetSysTagTargetWithTag] = Field(default_factory=list, description='标签列表')
    categories: list[GetSysCatTargetWithCat] = Field(default_factory=list, description='分类列表')


class GetPomodoroHabitCheckinDetail(SchemaBase):
    """番茄习惯打卡详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='打卡 ID')
    user_id: int = Field(description='用户 ID')
    habit_id: int = Field(description='习惯 ID')
    checkin_date: date = Field(description='打卡日期')
    count: int = Field(description='打卡次数')
    checked_at: datetime = Field(description='最近打卡时间')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
