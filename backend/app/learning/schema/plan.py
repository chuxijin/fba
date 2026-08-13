from datetime import date, datetime
from typing import Any

from pydantic import ConfigDict, Field, model_validator

from backend.app.learning.enums import (
    LearningDeliverySource,
    LearningDeliveryStatus,
    LearningPlanSource,
    LearningPlanStatus,
)
from backend.common.schema import SchemaBase


class LearningPlanSchemaBase(SchemaBase):
    title: str = Field(min_length=1, max_length=255, description='计划标题')
    start_date: date = Field(description='开始日期')
    end_date: date | None = Field(None, description='结束日期')
    source_type: LearningPlanSource = Field(LearningPlanSource.user, description='计划来源')
    status: LearningPlanStatus = Field(LearningPlanStatus.draft, description='计划状态')
    description: str | None = Field(None, description='计划说明')
    settings: dict[str, Any] | None = Field(None, description='计划设置')

    @model_validator(mode='after')
    def validate_dates(self) -> 'LearningPlanSchemaBase':
        if self.end_date is not None and self.end_date < self.start_date:
            raise ValueError('结束日期不能早于开始日期')
        return self


class CreateLearningPlanParam(LearningPlanSchemaBase):
    user_id: int = Field(gt=0, description='用户 ID')
    delivery_id: int | None = Field(None, gt=0, description='来源交付单 ID')


class CreateMyLearningPlanParam(LearningPlanSchemaBase):
    """用户自建计划参数，不暴露用户和交付单归属字段。"""


class UpdateLearningPlanParam(SchemaBase):
    title: str | None = Field(None, min_length=1, max_length=255, description='计划标题')
    start_date: date | None = Field(None, description='开始日期')
    end_date: date | None = Field(None, description='结束日期')
    source_type: LearningPlanSource | None = Field(None, description='计划来源')
    status: LearningPlanStatus | None = Field(None, description='计划状态')
    delivery_id: int | None = Field(None, gt=0, description='来源交付单 ID')
    description: str | None = Field(None, description='计划说明')
    settings: dict[str, Any] | None = Field(None, description='计划设置')


class GetLearningPlanDetail(LearningPlanSchemaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='计划 ID')
    user_id: int = Field(description='用户 ID')
    delivery_id: int | None = Field(None, description='交付单 ID')
    template_id: int | None = Field(None, description='来源模板 ID')
    template_name: str | None = Field(None, description='来源模板名称')
    username: str | None = Field(None, description='用户名')
    nickname: str | None = Field(None, description='用户昵称')
    task_count: int = Field(0, description='任务数量')
    completed_task_count: int = Field(0, description='已完成任务数量')
    created_by: int = Field(description='创建者 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class DeliveryPlanParam(SchemaBase):
    template_id: int | None = Field(None, gt=0, description='用于生成计划的模板 ID')
    title: str | None = Field(None, min_length=1, max_length=255, description='同步创建的计划标题')
    start_date: date = Field(description='计划开始日期')
    end_date: date | None = Field(None, description='计划结束日期')
    description: str | None = Field(None, description='计划说明')

    @model_validator(mode='after')
    def validate_plan_source(self) -> 'DeliveryPlanParam':
        if self.template_id is None and not self.title:
            raise ValueError('未选择模板时必须填写计划标题')
        return self


class CreateLearningDeliveryParam(SchemaBase):
    user_id: int | None = Field(None, gt=0, description='接收用户 ID')
    source_type: LearningDeliverySource = Field(LearningDeliverySource.external_order, description='交付来源')
    source_channel: str | None = Field(None, max_length=32, description='来源渠道')
    external_order_no: str | None = Field(None, max_length=128, description='外部订单号')
    external_customer_ref: str | None = Field(None, max_length=128, description='外部客户标识')
    requirements: dict[str, Any] | None = Field(None, description='定制需求')
    source_meta: dict[str, Any] | None = Field(None, description='来源扩展信息')
    assigned_to: int | None = Field(None, gt=0, description='负责人 ID')
    remark: str | None = Field(None, description='备注')
    plan: DeliveryPlanParam | None = Field(None, description='同步创建用户计划')


class UpdateLearningDeliveryParam(SchemaBase):
    user_id: int | None = Field(None, gt=0, description='接收用户 ID')
    source_type: LearningDeliverySource | None = Field(None, description='交付来源')
    source_channel: str | None = Field(None, max_length=32, description='来源渠道')
    external_order_no: str | None = Field(None, max_length=128, description='外部订单号')
    external_customer_ref: str | None = Field(None, max_length=128, description='外部客户标识')
    requirements: dict[str, Any] | None = Field(None, description='定制需求')
    source_meta: dict[str, Any] | None = Field(None, description='来源扩展信息')
    status: LearningDeliveryStatus | None = Field(None, description='交付状态')
    assigned_to: int | None = Field(None, gt=0, description='负责人 ID')
    remark: str | None = Field(None, description='备注')


class GetLearningDeliveryDetail(SchemaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='交付单 ID')
    delivery_no: str = Field(description='交付编号')
    user_id: int | None = Field(None, description='接收用户 ID')
    username: str | None = Field(None, description='用户名')
    nickname: str | None = Field(None, description='用户昵称')
    source_type: LearningDeliverySource = Field(description='交付来源')
    source_channel: str | None = Field(None, description='来源渠道')
    external_order_no: str | None = Field(None, description='外部订单号')
    external_customer_ref: str | None = Field(None, description='外部客户标识')
    requirements: dict[str, Any] | None = Field(None, description='定制需求')
    source_meta: dict[str, Any] | None = Field(None, description='来源扩展信息')
    status: LearningDeliveryStatus = Field(description='交付状态')
    assigned_to: int | None = Field(None, description='负责人 ID')
    delivered_by: int | None = Field(None, description='交付人 ID')
    delivered_at: datetime | None = Field(None, description='交付时间')
    remark: str | None = Field(None, description='备注')
    plan_id: int | None = Field(None, description='新建计划 ID')
    plan_title: str | None = Field(None, description='新建计划标题')
    template_id: int | None = Field(None, description='来源模板 ID')
    template_name: str | None = Field(None, description='来源模板名称')
    task_count: int = Field(0, description='本次交付任务数量')
    created_by: int = Field(description='创建者 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
