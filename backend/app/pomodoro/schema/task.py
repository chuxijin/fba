#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date, datetime

from pydantic import ConfigDict, Field

from backend.app.admin.schema.tag import GetSysTagTargetWithTag
from backend.app.admin.schema.cat import GetSysCatTargetWithCat
from backend.app.pomodoro.enums import PomodoroRepeatType, PomodoroTaskStatus
from backend.common.schema import SchemaBase


class PomodoroTaskSchemaBase(SchemaBase):
    """番茄任务基础模型"""

    title: str = Field(description='任务标题', min_length=1, max_length=100)
    description: str | None = Field(None, description='任务描述')
    priority: int = Field(0, ge=0, le=10, description='优先级')
    estimated_minutes: int | None = Field(None, ge=1, le=10080, description='预计完成分钟数')
    due_at: datetime | None = Field(None, description='截止时间')
    repeat_type: PomodoroRepeatType = Field(PomodoroRepeatType.none, description='重复类型')
    repeat_days: str | None = Field(None, description='自定义重复星期，逗号分隔，0=周一...6=周日')
    parent_id: int | None = Field(None, description='父任务 ID')
    schedule_date: date | None = Field(None, description='计划日期')


class CreatePomodoroTaskParam(PomodoroTaskSchemaBase):
    """创建番茄任务参数"""


class CreatePomodoroTaskInternal(PomodoroTaskSchemaBase):
    """创建番茄任务内部参数"""

    user_id: int = Field(description='用户 ID')
    status: PomodoroTaskStatus = Field(PomodoroTaskStatus.pending, description='任务状态')
    source_task_id: int | None = Field(None, description='重复来源任务 ID')
    repeat_key: str | None = Field(None, description='重复实例唯一键')


class UpdatePomodoroTaskParam(SchemaBase):
    """更新番茄任务参数"""

    title: str | None = Field(None, min_length=1, max_length=100, description='任务标题')
    description: str | None = Field(None, description='任务描述')
    priority: int | None = Field(None, ge=0, le=10, description='优先级')
    estimated_minutes: int | None = Field(None, ge=1, le=10080, description='预计完成分钟数')
    due_at: datetime | None = Field(None, description='截止时间')
    repeat_type: PomodoroRepeatType | None = Field(None, description='重复类型')
    repeat_days: str | None = Field(None, description='自定义重复星期，逗号分隔，0=周一...6=周日')
    status: PomodoroTaskStatus | None = Field(None, description='任务状态')
    parent_id: int | None = Field(None, description='父任务 ID')
    schedule_date: date | None = Field(None, description='计划日期')


class GetPomodoroTaskDetail(PomodoroTaskSchemaBase):
    """番茄任务详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='任务 ID')
    user_id: int = Field(description='用户 ID')
    status: PomodoroTaskStatus = Field(description='任务状态')
    completed_at: datetime | None = Field(None, description='完成时间')
    source_task_id: int | None = Field(None, description='重复来源任务 ID')
    repeat_days: str | None = Field(None, description='自定义重复星期，逗号分隔，0=周一...6=周日')
    schedule_date: date | None = Field(None, description='计划日期')
    repeat_key: str | None = Field(None, description='重复实例唯一键')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
    tags: list[GetSysTagTargetWithTag] = Field(default_factory=list, description='标签列表')
    categories: list[GetSysCatTargetWithCat] = Field(default_factory=list, description='分类列表')


class GetPomodoroTaskListItem(GetPomodoroTaskDetail):
    """番茄任务列表项"""

    children_count: int = Field(default=0, description='子任务数量')


class GeneratePomodoroRepeatTaskParam(SchemaBase):
    """生成重复任务参数"""

    target_date: date | None = Field(None, description='目标日期')


class GetPomodoroRepeatTaskGenerateResult(SchemaBase):
    """重复任务生成结果"""

    target_date: date = Field(description='目标日期')
    created_count: int = Field(description='创建数量')
    task_ids: list[int] = Field(description='任务 ID 列表')
