from datetime import date, datetime
from typing import Any

from pydantic import ConfigDict, Field, model_validator

from backend.app.learning.enums import (
    LearningActionType,
    LearningResourceType,
    LearningTemplateStatus,
)
from backend.app.learning.schema.task import LearningTaskGoalParam, LearningTaskKnowledgePointParam
from backend.common.schema import SchemaBase


class LearningPlanTemplateSchemaBase(SchemaBase):
    code: str = Field(min_length=1, max_length=64, description='模板编码')
    name: str = Field(min_length=1, max_length=255, description='模板名称')
    exam_type: str | None = Field(None, max_length=64, description='适用考试类型')
    version: int = Field(1, ge=1, description='模板版本')
    duration_days: int = Field(30, ge=1, le=3650, description='计划周期天数')
    default_daily_minutes: int = Field(120, ge=0, le=1440, description='默认每日学习分钟数')
    status: LearningTemplateStatus = Field(LearningTemplateStatus.draft, description='模板状态')
    description: str | None = Field(None, description='模板说明')
    settings: dict[str, Any] | None = Field(None, description='模板设置')


class CreateLearningPlanTemplateParam(LearningPlanTemplateSchemaBase):
    """创建计划模板参数。"""


class UpdateLearningPlanTemplateParam(SchemaBase):
    code: str | None = Field(None, min_length=1, max_length=64, description='模板编码')
    name: str | None = Field(None, min_length=1, max_length=255, description='模板名称')
    exam_type: str | None = Field(None, max_length=64, description='适用考试类型')
    version: int | None = Field(None, ge=1, description='模板版本')
    duration_days: int | None = Field(None, ge=1, le=3650, description='计划周期天数')
    default_daily_minutes: int | None = Field(None, ge=0, le=1440, description='默认每日学习分钟数')
    status: LearningTemplateStatus | None = Field(None, description='模板状态')
    description: str | None = Field(None, description='模板说明')
    settings: dict[str, Any] | None = Field(None, description='模板设置')


class GetLearningPlanTemplateDetail(LearningPlanTemplateSchemaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='模板 ID')
    stage_count: int = Field(0, description='阶段数量')
    task_count: int = Field(0, description='任务数量')
    created_by: int = Field(description='创建者 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class LearningPlanTemplateStageSchemaBase(SchemaBase):
    name: str = Field(min_length=1, max_length=128, description='阶段名称')
    start_day: int = Field(ge=1, description='起始相对天数')
    end_day: int = Field(ge=1, description='结束相对天数')
    order_index: int = Field(0, ge=0, description='排序')
    description: str | None = Field(None, description='阶段说明')

    @model_validator(mode='after')
    def validate_days(self) -> 'LearningPlanTemplateStageSchemaBase':
        if self.end_day < self.start_day:
            raise ValueError('阶段结束天数不能早于开始天数')
        return self


class CreateLearningPlanTemplateStageParam(LearningPlanTemplateStageSchemaBase):
    template_id: int = Field(gt=0, description='模板 ID')


class UpdateLearningPlanTemplateStageParam(SchemaBase):
    name: str | None = Field(None, min_length=1, max_length=128, description='阶段名称')
    start_day: int | None = Field(None, ge=1, description='起始相对天数')
    end_day: int | None = Field(None, ge=1, description='结束相对天数')
    order_index: int | None = Field(None, ge=0, description='排序')
    description: str | None = Field(None, description='阶段说明')


class GetLearningPlanTemplateStageDetail(LearningPlanTemplateStageSchemaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='阶段 ID')
    template_id: int = Field(description='模板 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class LearningPlanTemplateTaskSchemaBase(SchemaBase):
    relative_day: int = Field(ge=1, le=3650, description='相对计划开始的第几天')
    stage_id: int | None = Field(None, gt=0, description='模板阶段 ID')
    order_index: int = Field(0, ge=0, description='当日排序')
    title: str = Field(min_length=1, max_length=255, description='任务标题')
    action_type: LearningActionType = Field(LearningActionType.custom, description='学习行为')
    resource_type: LearningResourceType = Field(LearningResourceType.none, description='资源类型')
    resource_id: int | None = Field(None, gt=0, description='资源 ID')
    resource_key: str | None = Field(None, max_length=128, description='资源业务键')
    resource_version_id: int | None = Field(None, gt=0, description='资源版本 ID')
    resource_config: dict[str, Any] | None = Field(None, description='资源启动配置')
    expected_minutes: int = Field(15, ge=0, le=1440, description='预计用时分钟')
    description: str | None = Field(None, description='任务说明')
    knowledge_points: list[LearningTaskKnowledgePointParam] = Field(default_factory=list, description='知识点归属')
    goals: list[LearningTaskGoalParam] = Field(default_factory=list, description='完成目标')


class CreateLearningPlanTemplateTaskParam(LearningPlanTemplateTaskSchemaBase):
    template_id: int = Field(gt=0, description='模板 ID')


class UpdateLearningPlanTemplateTaskParam(SchemaBase):
    relative_day: int | None = Field(None, ge=1, le=3650, description='相对计划开始的第几天')
    stage_id: int | None = Field(None, gt=0, description='模板阶段 ID')
    order_index: int | None = Field(None, ge=0, description='当日排序')
    title: str | None = Field(None, min_length=1, max_length=255, description='任务标题')
    action_type: LearningActionType | None = Field(None, description='学习行为')
    resource_type: LearningResourceType | None = Field(None, description='资源类型')
    resource_id: int | None = Field(None, gt=0, description='资源 ID')
    resource_key: str | None = Field(None, max_length=128, description='资源业务键')
    resource_version_id: int | None = Field(None, gt=0, description='资源版本 ID')
    resource_config: dict[str, Any] | None = Field(None, description='资源启动配置')
    expected_minutes: int | None = Field(None, ge=0, le=1440, description='预计用时分钟')
    description: str | None = Field(None, description='任务说明')
    knowledge_points: list[LearningTaskKnowledgePointParam] | None = Field(None, description='知识点归属')
    goals: list[LearningTaskGoalParam] | None = Field(None, description='完成目标')


class GetLearningPlanTemplateTaskKnowledgePointDetail(LearningTaskKnowledgePointParam):
    id: int = Field(description='关联 ID')
    knowledge_point_code: str | None = Field(None, description='知识点编码')
    knowledge_point_name: str | None = Field(None, description='知识点名称')
    knowledge_point_path: str | None = Field(None, description='知识点路径')
    knowledge_system_name: str | None = Field(None, description='知识体系名称')


class GetLearningPlanTemplateTaskGoalDetail(LearningTaskGoalParam):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='目标 ID')


class GetLearningPlanTemplateTaskDetail(LearningPlanTemplateTaskSchemaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='模板任务 ID')
    template_id: int = Field(description='模板 ID')
    stage_name: str | None = Field(None, description='阶段名称')
    knowledge_points: list[GetLearningPlanTemplateTaskKnowledgePointDetail] = Field(
        default_factory=list,
        description='知识点归属',
    )
    goals: list[GetLearningPlanTemplateTaskGoalDetail] = Field(default_factory=list, description='完成目标')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class InstantiateLearningPlanParam(SchemaBase):
    user_id: int = Field(gt=0, description='接收用户 ID')
    start_date: date = Field(description='计划开始日期')
    title: str | None = Field(None, min_length=1, max_length=255, description='计划标题')
    delivery_id: int | None = Field(None, gt=0, description='来源交付单 ID')
    description: str | None = Field(None, description='计划说明')


class InstantiateLearningDeliveryPlanParam(SchemaBase):
    template_id: int = Field(gt=0, description='计划模板 ID')
    start_date: date = Field(description='计划开始日期')
    title: str | None = Field(None, min_length=1, max_length=255, description='计划标题')
    description: str | None = Field(None, description='计划说明')
