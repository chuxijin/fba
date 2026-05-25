#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class InboundReceiveParam(SchemaBase):
    """入站接收参数 (结构化模式)"""

    event_type: str = Field(min_length=1, description='事件类型')
    data: dict[str, Any] | str = Field(description='事件数据')
    event_id: str | None = Field(None, description='事件 ID (用于幂等)')


class InboundReceiveResult(SchemaBase):
    """入站接收结果"""

    status: str = Field(description='处理状态 (received/duplicate)')
    event_id: str | None = Field(None, description='事件 ID')
    event_type: str | None = Field(None, description='事件类型')
    log_id: int | None = Field(None, description='日志记录 ID')


class GetEventLogDetail(SchemaBase):
    """入站事件日志详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='日志 ID')
    uid: str = Field(description='日志唯一标识')
    source: str = Field(description='事件来源')
    event_type: str = Field(description='事件类型')
    event_id: str | None = Field(None, description='外部事件 ID')
    payload: str = Field(description='原始请求体')
    signature_valid: bool = Field(description='签名验证结果')
    status: int = Field(description='状态 (0:received 1:processed 2:failed)')
    error_message: str | None = Field(None, description='错误信息')
    processed_at: datetime | None = Field(None, description='处理时间')
    source_ip: str | None = Field(None, description='请求来源 IP')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class EventLogListParam(SchemaBase):
    """入站事件日志列表查询参数"""

    source: str | None = Field(None, description='事件来源')
    event_type: str | None = Field(None, description='事件类型')
    status: int | None = Field(None, description='状态')
    start_time: str | None = Field(None, description='开始时间')
    end_time: str | None = Field(None, description='结束时间')
