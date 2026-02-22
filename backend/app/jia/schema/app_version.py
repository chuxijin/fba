#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class CreateAppVersionParam(SchemaBase):
    """创建应用版本参数"""

    version: str = Field(description='版本号(如 1.0.3)')
    build_number: int = Field(description='构建号')
    download_url: str = Field(description='下载链接')
    changelog: str | None = Field(None, description='更新日志')
    force_update: bool = Field(default=False, description='是否强制更新')


class GetAppVersionDetail(SchemaBase):
    """应用版本详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='ID')
    platform: str = Field(description='平台')
    version: str = Field(description='版本号')
    build_number: int = Field(description='构建号')
    download_url: str = Field(description='下载链接')
    changelog: str | None = Field(None, description='更新日志')
    force_update: bool = Field(description='是否强制更新')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
