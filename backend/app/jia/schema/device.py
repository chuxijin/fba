#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import Field

from backend.common.schema import SchemaBase


class DeviceRegisterParam(SchemaBase):
    """设备注册参数"""

    device_id: str = Field(description='设备唯一标识')
    fcm_token: str = Field(description='FCM Token')
    device_name: str | None = Field(None, description='设备名称')
    device_type: str | None = Field(None, description='设备类型 (android/ios)')


class DeviceUpdateParam(SchemaBase):
    """设备更新参数"""

    fcm_token: str | None = Field(None, description='FCM Token')
    device_name: str | None = Field(None, description='设备名称')
    is_active: bool | None = Field(None, description='是否活跃')


class GetDeviceDetail(SchemaBase):
    """设备详情"""

    id: int = Field(description='设备 ID')
    user_id: int = Field(description='用户 ID')
    device_id: str = Field(description='设备唯一标识')
    fcm_token: str = Field(description='FCM Token')
    device_name: str | None = Field(None, description='设备名称')
    device_type: str | None = Field(None, description='设备类型')
    is_active: bool = Field(description='是否活跃')
    last_active_time: datetime | None = Field(None, description='最后活跃时间')
