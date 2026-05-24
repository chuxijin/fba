#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class CreateEndpointParam(SchemaBase):
    """创建出站端点参数"""

    name: str = Field(min_length=1, max_length=100, description='端点名称')
    url: str = Field(min_length=1, max_length=500, description='目标 URL')
    description: str | None = Field(None, max_length=500, description='描述')
    event_types: list[str] = Field(min_length=1, description='订阅的事件类型列表')
    headers: dict[str, Any] | None = Field(None, description='自定义请求头')
    max_retries: int = Field(5, ge=1, le=10, description='最大重试次数')
    timeout_seconds: int = Field(30, ge=5, le=120, description='超时秒数')


class UpdateEndpointParam(SchemaBase):
    """更新出站端点参数"""

    name: str | None = Field(None, max_length=100, description='端点名称')
    url: str | None = Field(None, max_length=500, description='目标 URL')
    description: str | None = Field(None, max_length=500, description='描述')
    event_types: list[str] | None = Field(None, description='订阅的事件类型列表')
    headers: dict[str, Any] | None = Field(None, description='自定义请求头')
    is_active: bool | None = Field(None, description='是否启用')
    max_retries: int | None = Field(None, ge=1, le=10, description='最大重试次数')
    timeout_seconds: int | None = Field(None, ge=5, le=120, description='超时秒数')


class GetEndpointDetail(SchemaBase):
    """出站端点详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='端点 ID')
    uid: str = Field(description='端点唯一标识')
    name: str = Field(description='端点名称')
    url: str = Field(description='目标 URL')
    description: str | None = Field(None, description='描述')
    event_types: list[str] = Field(description='订阅的事件类型列表')
    headers: dict[str, Any] | None = Field(None, description='自定义请求头')
    is_active: bool = Field(description='是否启用')
    failure_count: int = Field(description='连续失败次数')
    max_retries: int = Field(description='最大重试次数')
    timeout_seconds: int = Field(description='超时秒数')
    last_success_at: datetime | None = Field(None, description='最后成功时间')
    last_failure_at: datetime | None = Field(None, description='最后失败时间')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class EndpointListParam(SchemaBase):
    """端点列表查询参数"""

    name: str | None = Field(None, description='端点名称')
    is_active: bool | None = Field(None, description='是否启用')
    event_type: str | None = Field(None, description='订阅的事件类型')


class RotateSecretResult(SchemaBase):
    """密钥轮换结果"""

    uid: str = Field(description='端点唯一标识')
    new_secret: str = Field(description='新密钥 (whsec_ 开头)')
    message: str = Field(description='提示信息')


class TestEndpointResult(SchemaBase):
    """测试推送结果"""

    success: bool = Field(description='是否成功')
    status_code: int | None = Field(None, description='HTTP 响应码')
    response_body: str | None = Field(None, description='响应体')
    message: str = Field(description='结果描述')
