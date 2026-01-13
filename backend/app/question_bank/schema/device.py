#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pydantic import Field

from backend.common.schema import SchemaBase


class UpdateDeviceParam(SchemaBase):
    """更新设备信息参数"""

    device_id: str = Field(description='设备唯一标识')
    device_model: str | None = Field(None, description='设备型号')
    os_version: str | None = Field(None, description='操作系统版本')
    app_version: str | None = Field(None, description='App 版本')
    push_token: str | None = Field(None, description='推送 Token')
