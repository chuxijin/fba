#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.app.pomodoro.enums import PomodoroBreakStatus, PomodoroBreakType, PomodoroSource
from backend.common.schema import SchemaBase


class StartPomodoroBreakParam(SchemaBase):
    """开始番茄休息参数"""

    focus_session_id: int | None = Field(None, description='关联专注记录 ID')
    break_type: PomodoroBreakType = Field(PomodoroBreakType.short, description='休息类型')
    planned_minutes: int | None = Field(None, ge=1, le=120, description='计划休息分钟数')


class CreatePomodoroBreakInternal(SchemaBase):
    """创建番茄休息内部参数"""

    user_id: int = Field(description='用户 ID')
    focus_session_id: int | None = Field(None, description='关联专注记录 ID')
    break_type: PomodoroBreakType = Field(PomodoroBreakType.short, description='休息类型')
    status: PomodoroBreakStatus = Field(PomodoroBreakStatus.running, description='休息状态')
    planned_minutes: int = Field(5, ge=1, le=120, description='计划休息分钟数')
    break_seconds: int = Field(0, ge=0, description='实际休息秒数')
    started_at: datetime = Field(description='服务端开始时间')
    source: PomodoroSource = Field(PomodoroSource.mini, description='来源')


class FinishPomodoroBreakParam(SchemaBase):
    """完成番茄休息参数"""

    break_seconds: int = Field(0, ge=0, description='实际休息秒数')


class GetPomodoroBreakSessionDetail(SchemaBase):
    """番茄休息详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='休息记录 ID')
    user_id: int = Field(description='用户 ID')
    focus_session_id: int | None = Field(None, description='关联专注记录 ID')
    break_type: PomodoroBreakType = Field(description='休息类型')
    status: PomodoroBreakStatus = Field(description='休息状态')
    planned_minutes: int = Field(description='计划休息分钟数')
    break_seconds: int = Field(description='实际休息秒数')
    started_at: datetime = Field(description='服务端开始时间')
    ended_at: datetime | None = Field(None, description='结束时间')
    source: PomodoroSource = Field(description='来源')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
