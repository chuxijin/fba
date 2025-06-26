#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import Field

from backend.common.schema import SchemaBase


class CreateRedeemCodeParam(SchemaBase):
    """创建兑换码参数"""

    application_id: int = Field(description='应用ID')
    batch_no: str | None = Field(None, description='批次号')
    duration_days: int = Field(description='有效期天数')
    max_devices: int = Field(1, description='最大设备数量')
    expire_time: datetime | None = Field(None, description='过期时间')
    remark: str | None = Field(None, description='备注')


class CharTypeOptions(SchemaBase):
    """字符类型选项"""
    
    uppercase: bool = Field(True, description='大写字母')
    lowercase: bool = Field(True, description='小写字母')
    digits: bool = Field(True, description='数字')
    special: bool = Field(False, description='特殊字符')


class CardKeyGenerationRequest(SchemaBase):
    """卡密生成请求参数"""
    
    char_types: CharTypeOptions | None = Field(None, description='字符类型')
    key_length: int = Field(16, description='密钥长度')
    prefix: str | None = Field(None, description='前缀')
    suffix: str | None = Field(None, description='后缀')
    group_length: int | None = Field(None, description='分组长度')
    separator: str | None = Field(None, description='分隔符')
    count: int = Field(description='生成数量')


class BatchCreateRedeemCodeParam(SchemaBase):
    """批量创建兑换码参数"""

    application_id: int = Field(description='应用ID')
    batch_no: str = Field(description='批次号')
    duration_days: int = Field(description='有效期天数')
    max_devices: int = Field(1, description='最大设备数量')
    expire_time: datetime | None = Field(None, description='过期时间')
    remark: str | None = Field(None, description='备注')
    generation_params: CardKeyGenerationRequest = Field(description='生成参数')


class UseRedeemCodeParam(SchemaBase):
    """使用兑换码参数"""

    code: str = Field(description='兑换码')
    device_id: str = Field(description='设备标识')
    used_by: str | None = Field(None, description='使用者')


class RedeemCodeParam(SchemaBase):
    """兑换码使用参数"""

    code: str = Field(description='兑换码')
    device_id: str = Field(description='设备标识')
    used_by: str | None = Field(None, description='使用者')


class GetRedeemCodeDetail(SchemaBase):
    """兑换码详情"""

    id: int = Field(description='兑换码ID')
    code: str = Field(description='兑换码')
    application_id: int = Field(description='应用ID')
    batch_no: str | None = Field(description='批次号')
    duration_days: int = Field(description='有效期天数')
    max_devices: int = Field(description='最大设备数量')
    is_used: bool = Field(description='是否已使用')
    used_by: str | None = Field(description='使用者')
    used_time: datetime | None = Field(description='使用时间')
    expire_time: datetime | None = Field(description='过期时间')
    remark: str | None = Field(description='备注')
    created_time: datetime = Field(description='创建时间')