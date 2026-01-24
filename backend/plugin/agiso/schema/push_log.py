#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class GetPushLogDetail(BaseModel):
    """推送日志详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='日志ID')
    push_type: str = Field(description='推送类型')
    order_no: str = Field(description='订单编号')
    platform: str | None = Field(default=None, description='来源平台')
    push_data: str = Field(description='推送原始数据')
    process_status: int = Field(description='处理状态')
    process_result: str | None = Field(default=None, description='处理结果')
    error_message: str | None = Field(default=None, description='错误信息')
    retry_count: int = Field(description='重试次数')
    created_time: datetime = Field(description='创建时间')
    processed_time: datetime | None = Field(default=None, description='处理时间')
