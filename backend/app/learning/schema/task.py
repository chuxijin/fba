from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import ConfigDict, Field

from backend.app.learning.enums import LearningActionType, LearningResourceType, LearningTaskStatus
from backend.common.schema import SchemaBase


class LearningTaskKnowledgePointParam(SchemaBase):
    knowledge_system_id: int = Field(gt=0, description='知识体系 ID')
    knowledge_point_id: int = Field(gt=0, description='知识点 ID')
    role: str = Field('primary', pattern='^(primary|secondary)$', description='知识点角色')
    include_descendants: bool = Field(False, description='是否包含下级知识点')
    weight: Decimal = Field(Decimal(1), gt=0, le=1, description='归属权重')


class LearningTaskGoalParam(SchemaBase):
    metric: str = Field(min_length=1, max_length=32, description='目标指标')
    operator: str = Field('gte', pattern='^(gte|lte|eq)$', description='比较运算符')
    target_value: Decimal | None = Field(None, description='目标值')
    unit: str | None = Field(None, max_length=24, description='单位')
    is_required: bool = Field(True, description='是否必需')
    config: dict[str, Any] | None = Field(None, description='复杂目标配置')


class LearningTaskSchemaBase(SchemaBase):
    plan_date: date = Field(description='计划日期')
    order_index: int = Field(0, ge=0, description='当日排序')
    title: str = Field(min_length=1, max_length=255, description='任务标题')
    action_type: LearningActionType = Field(LearningActionType.custom, description='学习行为')
    resource_type: LearningResourceType = Field(LearningResourceType.none, description='资源类型')
    resource_id: int | None = Field(None, gt=0, description='资源 ID')
    resource_key: str | None = Field(None, max_length=128, description='资源业务键')
    resource_version_id: int | None = Field(None, gt=0, description='资源版本 ID')
    resource_config: dict[str, Any] | None = Field(None, description='资源启动配置')
    expected_minutes: int = Field(15, ge=0, le=1440, description='预计用时分钟')
    due_at: datetime | None = Field(None, description='截止时间')
    remind_at: datetime | None = Field(None, description='提醒时间')
    description: str | None = Field(None, description='任务说明')
    knowledge_points: list[LearningTaskKnowledgePointParam] = Field(default_factory=list, description='知识点归属')
    goals: list[LearningTaskGoalParam] = Field(default_factory=list, description='完成目标')


class CreateLearningTaskParam(LearningTaskSchemaBase):
    plan_id: int = Field(gt=0, description='计划 ID')
    delivery_id: int | None = Field(None, gt=0, description='交付单 ID')


class UpdateLearningTaskParam(SchemaBase):
    plan_date: date | None = Field(None, description='计划日期')
    order_index: int | None = Field(None, ge=0, description='当日排序')
    title: str | None = Field(None, min_length=1, max_length=255, description='任务标题')
    action_type: LearningActionType | None = Field(None, description='学习行为')
    resource_type: LearningResourceType | None = Field(None, description='资源类型')
    resource_id: int | None = Field(None, gt=0, description='资源 ID')
    resource_key: str | None = Field(None, max_length=128, description='资源业务键')
    resource_version_id: int | None = Field(None, gt=0, description='资源版本 ID')
    resource_config: dict[str, Any] | None = Field(None, description='资源启动配置')
    expected_minutes: int | None = Field(None, ge=0, le=1440, description='预计用时分钟')
    due_at: datetime | None = Field(None, description='截止时间')
    remind_at: datetime | None = Field(None, description='提醒时间')
    status: LearningTaskStatus | None = Field(None, description='任务状态')
    delivery_id: int | None = Field(None, gt=0, description='交付单 ID')
    description: str | None = Field(None, description='任务说明')
    knowledge_points: list[LearningTaskKnowledgePointParam] | None = Field(None, description='知识点归属')
    goals: list[LearningTaskGoalParam] | None = Field(None, description='完成目标')


class GetLearningTaskKnowledgePointDetail(LearningTaskKnowledgePointParam):
    id: int = Field(description='关联 ID')
    knowledge_point_code: str | None = Field(None, description='知识点编码')
    knowledge_point_name: str | None = Field(None, description='知识点名称')
    knowledge_point_path: str | None = Field(None, description='知识点路径')
    knowledge_system_name: str | None = Field(None, description='知识体系名称')


class GetLearningTaskGoalDetail(LearningTaskGoalParam):
    id: int = Field(description='目标 ID')


class GetLearningTaskDetail(LearningTaskSchemaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='任务 ID')
    plan_id: int = Field(description='计划 ID')
    user_id: int = Field(description='用户 ID')
    delivery_id: int | None = Field(None, description='交付单 ID')
    status: LearningTaskStatus = Field(description='任务状态')
    knowledge_points: list[GetLearningTaskKnowledgePointDetail] = Field(default_factory=list, description='知识点归属')
    goals: list[GetLearningTaskGoalDetail] = Field(default_factory=list, description='完成目标')
    created_by: int = Field(description='创建者 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class StartLearningTaskResult(SchemaBase):
    """任务启动结果，前端按 launch_type 决定跳到哪个页面"""

    task_id: int = Field(description='任务 ID')
    status: LearningTaskStatus = Field(description='启动后的任务状态')
    launch_type: Literal['ability', 'content', 'focus', 'practice'] = Field(description='启动方式')
    payload: dict[str, Any] | None = Field(None, description='启动参数')
    hint: str | None = Field(None, description='无法按预期启动时的提示文案')
