#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import Field

from backend.common.schema import SchemaBase


class CreateVersionParam(SchemaBase):
    """创建版本参数"""

    application_id: int = Field(description='应用ID')
    version_name: str = Field(description='版本名称')
    version_code: str = Field(description='版本号')
    description: str | None = Field(None, description='版本描述')
    download_url: str | None = Field(None, description='下载地址')
    file_size: str | None = Field(None, description='文件大小')
    file_hash: str | None = Field(None, description='文件哈希')
    is_force_update: bool = Field(False, description='是否强制更新')


class UpdateVersionParam(SchemaBase):
    """更新版本参数"""

    version_name: str | None = Field(None, description='版本名称')
    description: str | None = Field(None, description='版本描述')
    download_url: str | None = Field(None, description='下载地址')
    file_size: str | None = Field(None, description='文件大小')
    file_hash: str | None = Field(None, description='文件哈希')
    is_force_update: bool | None = Field(None, description='是否强制更新')
    is_latest: bool | None = Field(None, description='是否最新版本')
    status: int | None = Field(None, description='状态')


class GetVersionDetail(SchemaBase):
    """版本详情"""

    id: int = Field(description='版本ID')
    application_id: int = Field(description='应用ID')
    version_name: str = Field(description='版本名称')
    version_code: str = Field(description='版本号')
    description: str | None = Field(description='版本描述')
    download_url: str | None = Field(description='下载地址')
    file_size: str | None = Field(description='文件大小')
    file_hash: str | None = Field(description='文件哈希')
    is_force_update: bool = Field(description='是否强制更新')
    is_latest: bool = Field(description='是否最新版本')
    status: int = Field(description='状态')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(description='更新时间')