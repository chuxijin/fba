#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import Field

from backend.common.schema import SchemaBase


class CreateAuthorizationParam(SchemaBase):
    """创建授权参数"""

    application_id: int = Field(description='应用ID')
    device_id: int = Field(description='设备ID')
    auth_type: int = Field(description='授权类型')
    start_time: datetime = Field(description='授权开始时间')
    end_time: datetime | None = Field(None, description='授权结束时间')
    auth_source: str | None = Field(None, description='授权来源')
    remark: str | None = Field(None, description='备注')


class AuthorizeDeviceParam(SchemaBase):
    """手动授权设备参数"""

    application_id: int = Field(description='应用ID')
    device_id: str = Field(description='设备标识')
    duration_days: int = Field(description='授权天数')
    remark: str | None = Field(None, description='备注')


class RedeemCodeAuthParam(SchemaBase):
    """兑换码授权参数"""

    code: str = Field(description='兑换码')
    device_id: str = Field(description='设备标识')


class UpdateAuthorizationParam(SchemaBase):
    """更新授权参数"""

    status: int | None = Field(None, description='授权状态')
    end_time: datetime | None = Field(None, description='授权结束时间')
    remark: str | None = Field(None, description='备注')


class UpdateAuthorizationTimeParam(SchemaBase):
    """修改授权时间参数"""

    end_time: datetime | None = Field(None, description='新的结束时间，为空表示永久授权')
    remark: str | None = Field(None, description='修改备注')


class CheckAuthorizationParam(SchemaBase):
    """检查授权参数"""

    app_key: str = Field(description='应用标识')
    device_id: str = Field(description='设备标识')


class GetAuthorizationDetail(SchemaBase):
    """授权详情"""

    id: int = Field(description='授权ID')
    application_id: int = Field(description='应用ID')
    device_id: int = Field(description='设备ID')
    auth_type: int = Field(description='授权类型')
    status: int = Field(description='授权状态')
    start_time: datetime = Field(description='授权开始时间')
    end_time: datetime | None = Field(description='授权结束时间')
    remaining_days: int | None = Field(description='剩余天数')
    auth_source: str | None = Field(description='授权来源')
    remark: str | None = Field(description='备注')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(description='更新时间')


class AuthorizationCheckResult(SchemaBase):
    """授权检查结果"""

    is_authorized: bool = Field(description='是否已授权')
    status: int | None = Field(description='授权状态')
    remaining_days: int | None = Field(description='剩余天数')
    end_time: datetime | None = Field(description='授权结束时间')
    message: str = Field(description='提示信息')