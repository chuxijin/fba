from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field

from backend.app.learning.enums import LearningFocusMode, LearningFocusStatus
from backend.common.schema import SchemaBase


class StartLearningFocusParam(SchemaBase):
    planned_minutes: int = Field(25, ge=1, le=240, description='计划专注分钟')
    mode: LearningFocusMode = Field(LearningFocusMode.pomodoro, description='专注模式')


class AttachLearningFocusTaskParam(SchemaBase):
    task_id: int = Field(gt=0, description='要关联的学习任务 ID')


class FinishLearningFocusParam(SchemaBase):
    focused_seconds: int = Field(0, ge=0, description='客户端有效专注秒数')
    paused_seconds: int = Field(0, ge=0, description='客户端暂停秒数')
    interrupt_count: int = Field(0, ge=0, description='中断次数')
    remark: str | None = Field(None, description='备注')


class GetLearningFocusSessionDetail(SchemaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='专注记录 ID')
    task_id: int | None = Field(None, description='学习任务 ID，空表示自由专注')
    user_id: int = Field(description='用户 ID')
    mode: LearningFocusMode = Field(description='专注模式')
    status: LearningFocusStatus = Field(description='专注状态')
    planned_minutes: int = Field(description='计划专注分钟')
    focused_seconds: int = Field(description='有效专注秒数')
    paused_seconds: int = Field(description='暂停秒数')
    interrupt_count: int = Field(description='中断次数')
    started_at: datetime = Field(description='开始时间')
    paused_at: datetime | None = Field(None, description='暂停时间')
    ended_at: datetime | None = Field(None, description='结束时间')
    remark: str | None = Field(None, description='备注')
    task_title: str | None = Field(None, description='关联任务标题')


class CompleteLearningTaskParam(SchemaBase):
    metrics: dict[str, Any] = Field(default_factory=dict, description='实际完成指标')
    completion_source: str = Field('manual', max_length=32, description='完成来源')
    extra_data: dict[str, Any] | None = Field(None, description='扩展完成数据')


class GetLearningCompletionRecordDetail(SchemaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='完成记录 ID')
    task_id: int = Field(description='学习任务 ID')
    user_id: int = Field(description='用户 ID')
    completion_source: str = Field(description='完成来源')
    duration_seconds: int = Field(description='累计耗时秒数')
    actual_metrics: dict[str, Any] | None = Field(None, description='实际指标')
    extra_data: dict[str, Any] | None = Field(None, description='扩展数据')
    completed_at: datetime = Field(description='完成时间')
