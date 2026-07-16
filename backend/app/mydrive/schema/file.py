#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any

from pydantic import Field

from backend.common.schema import SchemaBase


class GetMyDriveFileDetail(SchemaBase):
    """文件详情"""

    file_id: str = Field(description='文件 ID')
    name: str = Field(description='文件名称')
    path: str = Field(description='文件路径')
    is_directory: bool = Field(description='是否为目录')
    size: int | None = Field(description='文件大小（字节）')
    parent_id: str | None = Field(description='父目录 ID')
    created_at: datetime | None = Field(description='创建时间')
    modified_at: datetime | None = Field(description='更新时间')
    hash_value: str | None = Field(description='文件哈希')
    extra: dict[str, Any] = Field(description='扩展信息')


class GetMyDriveFileList(SchemaBase):
    """文件列表"""

    items: list[GetMyDriveFileDetail] = Field(description='当前页文件')
    total: int = Field(description='目录文件总数')
    page: int = Field(description='当前页码')
    per_page: int = Field(description='每页文件数')
    path: str = Field(description='挂载内目录路径')


class MyDriveFileReference(SchemaBase):
    """文件定位参数"""

    file_id: str = Field(min_length=1, description='文件 ID')
    name: str = Field(min_length=1, description='文件名称')
    path: str = Field(min_length=1, description='文件路径')
    is_directory: bool = Field(default=False, description='是否为目录')
    parent_id: str | None = Field(default=None, description='父目录 ID')
    extra: dict[str, Any] = Field(default_factory=dict, description='文件扩展信息')


class CreateMyDriveDirectoryParam(SchemaBase):
    """创建目录参数"""

    name: str = Field(min_length=1, max_length=255, description='目录名称')
    parent: MyDriveFileReference | None = Field(default=None, description='父目录')


class OperateMyDriveFilesParam(SchemaBase):
    """文件操作参数"""

    files: list[MyDriveFileReference] = Field(min_length=1, description='待操作文件')
    target: MyDriveFileReference | None = Field(default=None, description='目标目录')


class RenameMyDriveFileParam(SchemaBase):
    """重命名文件参数"""

    file: MyDriveFileReference = Field(description='待重命名文件')
    name: str = Field(min_length=1, max_length=255, description='新名称')


class TransferMyDriveFilesParam(SchemaBase):
    """外部文件转存参数"""

    files: list[MyDriveFileReference] = Field(min_length=1, description='待转存文件')
    target_space_id: int = Field(gt=0, description='目标个人文件空间 ID')


class CreateMyDriveShareParam(SchemaBase):
    """创建分享参数"""

    files: list[MyDriveFileReference] = Field(min_length=1, description='待分享文件')
    title: str = Field(min_length=1, max_length=255, description='分享标题')
    expires_in_days: int = Field(default=0, description='有效期天数，0 表示永久')
    password: str = Field(default='', max_length=4, description='四位分享提取码')


class GetMyDriveShareDetail(SchemaBase):
    """分享详情"""

    provider: str = Field(description='网盘 Provider')
    share_id: str = Field(description='分享 ID')
    title: str = Field(description='分享标题')
    url: str = Field(description='分享链接')
    password: str = Field(description='分享提取码')
    expires_in_days: int = Field(description='有效期天数')
    expired_at: datetime | None = Field(description='过期时间')


class GetMyDriveShareList(SchemaBase):
    """分享列表"""

    items: list[GetMyDriveShareDetail] = Field(description='当前页分享')
    total: int = Field(description='分享总数')
    page: int = Field(description='当前页码')
    per_page: int = Field(description='每页分享数')


class CancelMyDriveSharesParam(SchemaBase):
    """取消分享参数"""

    share_ids: list[str] = Field(min_length=1, description='待取消分享 ID')
