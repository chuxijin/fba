#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.app.actcode.schema.code_config import CodeGeneratorConfig
from backend.common.schema import SchemaBase


class CreateBatchParam(SchemaBase):
    """创建批次参数"""

    app_id: str = Field(description='应用 ID')
    name: str = Field(description='批次名称')
    reward_type: str = Field(description='权益类型')
    reward_data: dict = Field(description='权益数据')
    total_count: int = Field(gt=0, le=100000, description='生成数量')
    valid_from: datetime | None = Field(None, description='有效期开始')
    valid_to: datetime | None = Field(None, description='有效期结束')
    max_use_per_code: int = Field(default=1, gt=0, description='单码最大使用次数')
    generator_config: CodeGeneratorConfig | None = Field(None, description='生成器配置')


class UpdateBatchParam(SchemaBase):
    """更新批次参数"""

    name: str | None = Field(None, description='批次名称')
    status: int | None = Field(None, ge=0, le=1, description='状态')


class GetBatchDetail(SchemaBase):
    """批次详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='批次 ID')
    app_id: str = Field(description='应用 ID')
    batch_no: str = Field(description='批次编号')
    name: str = Field(description='批次名称')
    reward_type: str = Field(description='权益类型')
    reward_data: dict = Field(description='权益数据')
    generator_config: dict | None = Field(None, description='生成器配置')
    total_count: int = Field(description='总数量')
    used_count: int = Field(description='已使用数量')
    valid_from: datetime | None = Field(None, description='有效期开始')
    valid_to: datetime | None = Field(None, description='有效期结束')
    max_use_per_code: int = Field(description='单码最大使用次数')
    status: int = Field(description='状态')
    created_time: datetime = Field(description='创建时间')


class GetActcodeDetail(SchemaBase):
    """激活码详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='激活码 ID')
    batch_id: int = Field(description='批次 ID')
    code: str = Field(description='激活码')
    used_count: int = Field(description='已使用次数')
    status: int = Field(description='状态')
    created_time: datetime = Field(description='创建时间')


class RedeemCodeParam(SchemaBase):
    """兑换激活码参数"""

    app_id: str = Field(description='应用 ID')
    code: str = Field(min_length=1, max_length=64, description='激活码')
    user_id: str = Field(description='用户 ID')
    ip_address: str | None = Field(None, description='IP 地址')
    device_info: str | None = Field(None, description='设备信息')


class RedeemCodeResult(SchemaBase):
    """兑换结果"""

    success: bool = Field(description='是否成功')
    reward_type: str = Field(description='权益类型')
    reward_data: dict = Field(description='权益数据')
    message: str = Field(description='提示信息')


class GetUsageDetail(SchemaBase):
    """使用记录详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='记录 ID')
    code_id: int = Field(description='激活码 ID')
    app_id: str = Field(description='应用 ID')
    user_id: str = Field(description='用户 ID')
    used_time: datetime = Field(description='使用时间')
    ip_address: str | None = Field(None, description='IP 地址')
    device_info: str | None = Field(None, description='设备信息')
