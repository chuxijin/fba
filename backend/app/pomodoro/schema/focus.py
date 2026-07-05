#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.app.pomodoro.enums import PomodoroFocusMode, PomodoroFocusStatus, PomodoroSource
from backend.common.schema import SchemaBase


class StartPomodoroFocusParam(SchemaBase):
    """开始番茄专注参数"""

    task_id: int | None = Field(None, description='关联任务 ID')
    mode: PomodoroFocusMode = Field(PomodoroFocusMode.pomodoro, description='专注模式')
    planned_minutes: int = Field(25, ge=1, le=240, description='计划专注分钟数')
    client_started_at: datetime | None = Field(None, description='客户端开始时间')


class CreatePomodoroFocusInternal(StartPomodoroFocusParam):
    """创建番茄专注内部参数"""

    user_id: int = Field(description='用户 ID')
    status: PomodoroFocusStatus = Field(PomodoroFocusStatus.running, description='专注状态')
    focused_seconds: int = Field(0, ge=0, description='实际专注秒数')
    paused_seconds: int = Field(0, ge=0, description='暂停秒数')
    interrupt_count: int = Field(0, ge=0, description='中断次数')
    started_at: datetime = Field(description='服务端开始时间')
    source: PomodoroSource = Field(PomodoroSource.mini, description='来源')


class FinishPomodoroFocusParam(SchemaBase):
    """完成番茄专注参数"""

    focused_seconds: int = Field(0, ge=0, description='实际专注秒数')
    paused_seconds: int = Field(0, ge=0, description='暂停秒数')
    interrupt_count: int = Field(0, ge=0, description='中断次数')
    remark: str | None = Field(None, description='备注')


class GetPomodoroFocusSessionDetail(SchemaBase):
    """番茄专注详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='专注记录 ID')
    user_id: int = Field(description='用户 ID')
    task_id: int | None = Field(None, description='关联任务 ID')
    mode: PomodoroFocusMode = Field(description='专注模式')
    status: PomodoroFocusStatus = Field(description='专注状态')
    planned_minutes: int = Field(description='计划专注分钟数')
    focused_seconds: int = Field(description='实际专注秒数')
    paused_seconds: int = Field(description='暂停秒数')
    interrupt_count: int = Field(description='中断次数')
    started_at: datetime = Field(description='服务端开始时间')
    paused_at: datetime | None = Field(None, description='最近暂停时间')
    ended_at: datetime | None = Field(None, description='结束时间')
    client_started_at: datetime | None = Field(None, description='客户端开始时间')
    source: PomodoroSource = Field(description='来源')
    remark: str | None = Field(None, description='备注')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetPomodoroFocusRecordItem(GetPomodoroFocusSessionDetail):
    """番茄专注记录列表项"""
