#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import Field

from backend.common.schema import SchemaBase


class CreateDeviceParam(SchemaBase):
    """创建设备参数"""

    device_id: str = Field(description='设备唯一标识')
    device_name: str | None = Field(None, description='设备名称')
    device_type: str | None = Field(None, description='设备类型')
    os_info: str | None = Field(None, description='操作系统信息')
    ip_address: str | None = Field(None, description='IP地址')


class UpdateDeviceParam(SchemaBase):
    """更新设备参数"""

    device_name: str | None = Field(None, description='设备名称')
    device_type: str | None = Field(None, description='设备类型')
    os_info: str | None = Field(None, description='操作系统信息')
    ip_address: str | None = Field(None, description='IP地址')
    status: int | None = Field(None, description='状态')


class GetDeviceDetail(SchemaBase):
    """设备详情"""

    id: int = Field(description='设备ID')
    device_id: str = Field(description='设备唯一标识')
    device_name: str | None = Field(description='设备名称')
    device_type: str | None = Field(description='设备类型')
    os_info: str | None = Field(description='操作系统信息')
    ip_address: str | None = Field(description='IP地址')
    status: int = Field(description='状态')
    first_seen: datetime = Field(description='首次发现时间')
    last_seen: datetime | None = Field(description='最后活跃时间')