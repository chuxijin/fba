#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class GetDeliveryDetail(SchemaBase):
    """投递记录详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='投递记录 ID')
    uid: str = Field(description='投递唯一标识')
    endpoint_id: int = Field(description='端点 ID')
    event_id: str = Field(description='事件 ID')
    event_type: str = Field(description='事件类型')
    status: int = Field(description='投递状态 (0:pending 1:success 2:failed 3:retrying)')
    response_code: int | None = Field(None, description='HTTP 响应码')
    response_body: str | None = Field(None, description='响应体')
    attempt_count: int = Field(description='已尝试次数')
    next_retry_at: datetime | None = Field(None, description='下次重试时间')
    completed_at: datetime | None = Field(None, description='完成时间')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class DeliveryListParam(SchemaBase):
    """投递记录列表查询参数"""

    endpoint_id: int | None = Field(None, description='端点 ID')
    event_type: str | None = Field(None, description='事件类型')
    status: int | None = Field(None, description='投递状态')
    start_time: str | None = Field(None, description='开始时间')
    end_time: str | None = Field(None, description='结束时间')
