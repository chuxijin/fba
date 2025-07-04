#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field, field_validator

from backend.common.schema import SchemaBase


class WebhookSchemaBase(SchemaBase):
    """Webhook基础模型"""

    event_type: str = Field(description='事件类型')
    source: str = Field(description='事件来源')
    webhook_url: str | None = Field(None, description='Webhook URL')
    headers: dict[str, Any] | None = Field(None, description='请求头信息')
    payload: str = Field(description='事件数据')
    status: int = Field(1, description='处理状态（0：失败、1：成功、2：待处理）')
    error_message: str | None = Field(None, description='错误信息')
    processed_at: str | None = Field(None, description='处理时间')
    retry_count: int = Field(0, description='重试次数')


class CreateWebhookParam(SchemaBase):
    """创建Webhook事件参数"""

    event_type: str = Field(description='事件类型')
    source: str = Field(description='事件来源')
    webhook_url: str | None = Field(None, description='Webhook URL')
    headers: dict[str, Any] | None = Field(None, description='请求头信息')
    payload: dict[str, Any] | str = Field(description='事件数据')


class UpdateWebhookParam(SchemaBase):
    """更新Webhook事件参数"""

    status: int = Field(description='处理状态（0：失败、1：成功、2：待处理）')
    error_message: str | None = Field(None, description='错误信息')
    processed_at: str | None = Field(None, description='处理时间')
    retry_count: int = Field(0, description='重试次数')


class DeleteWebhookParam(SchemaBase):
    """删除Webhook事件参数"""

    pks: list[int] = Field(description='Webhook事件 ID 列表')


class GetWebhookDetail(WebhookSchemaBase):
    """Webhook事件详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='Webhook事件 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class WebhookReceiveParam(SchemaBase):
    """接收Webhook事件参数"""

    event_type: str = Field(min_length=1, description='事件类型')
    data: dict[str, Any] | str = Field(description='事件数据')


class WebhookListParam(SchemaBase):
    """Webhook事件列表查询参数"""

    event_type: str | None = Field(None, description='事件类型')
    source: str | None = Field(None, description='事件来源')
    status: int | None = Field(None, description='处理状态')
    start_time: str | None = Field(None, description='开始时间')
    end_time: str | None = Field(None, description='结束时间')


class WebhookConfigParam(SchemaBase):
    """Webhook配置参数"""

    name: str = Field(description='配置名称')
    endpoint_url: str = Field(description='接收端点URL')
    secret_key: str | None = Field(None, description='密钥用于签名验证')
    required_headers: dict[str, str] | None = Field(None, description='必需的请求头')
    allowed_event_types: list[str] | None = Field(None, description='允许的事件类型')
    is_active: bool = Field(True, description='是否启用')


class HeaderValidationRule(SchemaBase):
    """Header验证规则"""

    header_name: str = Field(description='Header名称')
    header_value: str = Field(description='Header值')
    is_required: bool = Field(True, description='是否必需')
    validation_type: str = Field('exact', description='验证类型（exact：精确匹配，contains：包含，regex：正则）')
    
    @field_validator('validation_type')
    @classmethod
    def validate_validation_type(cls, v: str) -> str:
        """验证validation_type字段"""
        allowed_types = ['exact', 'contains', 'regex']
        if v not in allowed_types:
            raise ValueError(f'validation_type必须是以下值之一: {allowed_types}')
        return v


# ==================== WebhookConfig Schema ====================

class WebhookConfigBase(SchemaBase):
    """WebhookConfig基础Schema"""
    
    name: str = Field(description='配置名称')
    endpoint_url: str = Field(description='接收端点URL')
    secret_key: str | None = Field(None, description='密钥用于签名验证')
    required_headers: dict[str, Any] | None = Field(None, description='必需的请求头')
    allowed_event_types: list[str] | None = Field(None, description='允许的事件类型')
    is_active: bool = Field(True, description='是否启用')


class CreateWebhookConfigParam(WebhookConfigBase):
    """创建WebhookConfig参数"""
    pass


class UpdateWebhookConfigParam(SchemaBase):
    """更新WebhookConfig参数"""
    
    name: str | None = Field(None, description='配置名称')
    endpoint_url: str | None = Field(None, description='接收端点URL')
    secret_key: str | None = Field(None, description='密钥用于签名验证')
    required_headers: dict[str, Any] | None = Field(None, description='必需的请求头')
    allowed_event_types: list[str] | None = Field(None, description='允许的事件类型')
    is_active: bool | None = Field(None, description='是否启用')


class WebhookConfigListParam(SchemaBase):
    """WebhookConfig查询参数"""
    
    name: str | None = Field(None, description='配置名称')
    endpoint_url: str | None = Field(None, description='接收端点URL')
    is_active: bool | None = Field(None, description='是否启用')


class GetWebhookConfigDetail(WebhookConfigBase):
    """WebhookConfig详情"""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int = Field(description='配置ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class DeleteWebhookConfigParam(SchemaBase):
    """删除WebhookConfig参数"""
    
    pks: list[int] = Field(description='主键列表') 