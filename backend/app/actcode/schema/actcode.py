#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.app.actcode.schema.code_config import CodeGeneratorConfig
from backend.app.admin.schema.token import GetLoginToken
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


class OrderCodePayload(SchemaBase):
    """订单号参数"""

    order_input: str = Field(min_length=1, max_length=500, description='包含订单号的原始文本')


class OrderCodeVerifyResult(SchemaBase):
    """订单号校验结果"""

    valid: bool = Field(description='是否有效')
    order_no: str | None = Field(None, description='识别到的订单号')
    is_bound: bool = Field(default=False, description='是否已绑定账号')
    can_login: bool = Field(default=False, description='是否可直接登录')
    username: str | None = Field(None, description='已绑定的用户名')
    membership_plan_id: int | None = Field(None, description='会员计划 ID')
    message: str = Field(description='提示信息')


class OrderCodeActivateResult(SchemaBase):
    """订单号激活结果"""

    order_no: str = Field(description='订单号')
    user_id: int = Field(description='用户 ID')
    username: str = Field(description='用户名')
    just_activated: bool = Field(description='是否本次新完成激活')
    membership_plan_id: int | None = Field(None, description='会员计划 ID')
    tier_code: str | None = Field(None, description='会员等级编码')
    tier_name: str | None = Field(None, description='会员等级名称')
    membership_valid_to: datetime | None = Field(None, description='会员有效期至')
    message: str = Field(description='提示信息')


class OrderCodeLoginResult(GetLoginToken):
    """订单号登录结果"""

    order_no: str = Field(description='订单号')
    auto_created: bool = Field(description='是否自动创建了账号')
    just_activated: bool = Field(description='是否本次新完成激活')
    membership_plan_id: int | None = Field(None, description='会员计划 ID')
    tier_code: str | None = Field(None, description='会员等级编码')
    tier_name: str | None = Field(None, description='会员等级名称')
    membership_valid_to: datetime | None = Field(None, description='会员有效期至')
