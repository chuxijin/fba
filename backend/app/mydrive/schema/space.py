#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field, field_serializer

from backend.common.schema import SchemaBase


class CreateMyDriveSpaceParam(SchemaBase):
    """创建文件空间"""

    provider: str = Field(max_length=64, description='网盘驱动标识')
    space_type: str = Field(max_length=32, description='文件空间类型')
    name: str = Field(max_length=128, description='文件空间名称')
    source_key: str = Field(max_length=512, description='来源唯一标识')
    account_id: int | None = Field(default=None, description='网盘账户 ID')
    root_id: str | None = Field(default=None, max_length=512, description='根目录 ID')
    root_path: str = Field(default='/', max_length=1024, description='根目录路径')
    source_ref: dict[str, Any] = Field(default_factory=dict, description='来源定位信息')
    capabilities: list[str] = Field(default_factory=list, description='文件空间能力')


class PreviewMyDriveSpaceParam(SchemaBase):
    """预览文件空间"""

    provider: str = Field(max_length=64, description='网盘驱动标识')
    space_type: str = Field(max_length=32, description='文件空间类型')
    account_id: int = Field(description='网盘账户 ID')
    source_key: str = Field(default='', max_length=512, description='来源唯一标识')
    source_ref: dict[str, Any] = Field(default_factory=dict, description='来源定位信息')
    root_id: str | None = Field(default=None, max_length=512, description='根目录 ID')
    root_path: str = Field(default='/', max_length=1024, description='根目录路径')
    path: str = Field(default='/', max_length=1024, description='待预览目录路径')
    file_id: str | None = Field(default=None, max_length=512, description='待预览目录 ID')


class UpdateMyDriveSpaceParam(SchemaBase):
    """更新文件空间"""

    name: str | None = Field(default=None, max_length=128, description='文件空间名称')
    root_id: str | None = Field(default=None, max_length=512, description='根目录 ID')
    root_path: str | None = Field(default=None, max_length=1024, description='根目录路径')
    source_ref: dict[str, Any] | None = Field(default=None, description='来源定位信息')
    capabilities: list[str] | None = Field(default=None, description='文件空间能力')
    is_enabled: bool | None = Field(default=None, description='是否启用')


class GetMyDriveSpaceDetail(SchemaBase):
    """文件空间详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='文件空间 ID')
    owner_id: int = Field(description='所属用户 ID')
    provider: str = Field(description='网盘驱动标识')
    space_type: str = Field(description='文件空间类型')
    name: str = Field(description='文件空间名称')
    source_key: str = Field(description='来源唯一标识')
    account_id: int | None = Field(description='网盘账户 ID')
    root_id: str | None = Field(description='根目录 ID')
    root_path: str = Field(description='根目录路径')
    source_ref: dict[str, Any] = Field(description='来源定位信息')
    capabilities: list[str] = Field(description='文件空间能力')
    is_enabled: bool = Field(description='是否启用')
    last_scanned_at: datetime | None = Field(description='最近扫描时间')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(description='更新时间')

    @field_serializer('source_ref')
    def serialize_source_ref(self, source_ref: dict[str, Any]) -> dict[str, Any]:
        """隐藏来源敏感参数。"""
        return {key: value for key, value in source_ref.items() if key != 'passcode'}
