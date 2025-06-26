#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field, field_validator

from backend.common.schema import SchemaBase


class FileCacheBase(SchemaBase):
    """文件缓存基础信息"""
    
    file_id: str = Field(..., description="文件唯一ID")
    file_name: str = Field(..., description="文件名称")
    file_path: str = Field(..., description="文件路径")
    is_folder: bool = Field(False, description="是否为文件夹")
    parent_id: str | None = Field(None, description="父目录ID")
    drive_account_id: int = Field(..., description="关联网盘账户ID")
    file_size: int | None = Field(None, description="文件大小")
    file_created_at: str | None = Field(None, description="文件创建时间")
    file_updated_at: str | None = Field(None, description="文件更新时间")
    file_ext: dict[str, Any] | None = Field(None, description="扩展信息")
    cache_version: str | None = Field(None, description="缓存版本")
    is_valid: bool = Field(True, description="缓存是否有效")


class CreateFileCacheParam(FileCacheBase):
    """创建文件缓存参数"""
    
    @field_validator('file_ext', mode='before')
    @classmethod
    def validate_file_ext(cls, v: Any) -> dict[str, Any] | None:
        """验证扩展信息"""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("扩展信息必须是有效的JSON格式")
        if isinstance(v, dict):
            return v
        raise ValueError("扩展信息必须是字典或JSON字符串")


class UpdateFileCacheParam(SchemaBase):
    """更新文件缓存参数"""
    
    file_name: str | None = Field(None, description="文件名称")
    file_path: str | None = Field(None, description="文件路径")
    is_folder: bool | None = Field(None, description="是否为文件夹")
    parent_id: str | None = Field(None, description="父目录ID")
    file_size: int | None = Field(None, description="文件大小")
    file_created_at: str | None = Field(None, description="文件创建时间")
    file_updated_at: str | None = Field(None, description="文件更新时间")
    file_ext: dict[str, Any] | None = Field(None, description="扩展信息")
    cache_version: str | None = Field(None, description="缓存版本")
    is_valid: bool | None = Field(None, description="缓存是否有效")

    @field_validator('file_ext', mode='before')
    @classmethod
    def validate_file_ext(cls, v: Any) -> dict[str, Any] | None:
        """验证扩展信息"""
        if v is None:
            return None
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                raise ValueError("扩展信息必须是有效的JSON格式")
        if isinstance(v, dict):
            return v
        raise ValueError("扩展信息必须是字典或JSON字符串")


class GetFileCacheDetail(SchemaBase):
    """文件缓存详情"""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int = Field(..., description="缓存ID")
    file_id: str = Field(..., description="文件唯一ID")
    file_name: str = Field(..., description="文件名称")
    file_path: str = Field(..., description="文件路径")
    is_folder: bool = Field(..., description="是否为文件夹")
    parent_id: str | None = Field(None, description="父目录ID")
    drive_account_id: int = Field(..., description="关联网盘账户ID")
    file_size: int | None = Field(None, description="文件大小")
    file_created_at: str | None = Field(None, description="文件创建时间")
    file_updated_at: str | None = Field(None, description="文件更新时间")
    file_ext: str | None = Field(None, description="扩展信息JSON")
    cache_version: str | None = Field(None, description="缓存版本")
    is_valid: bool = Field(..., description="缓存是否有效")
    created_time: datetime = Field(..., description="创建时间")
    updated_time: datetime | None = Field(None, description="更新时间")

    @field_validator('file_ext', mode='after')
    @classmethod
    def parse_file_ext(cls, v: str | None) -> dict[str, Any] | None:
        """解析扩展信息"""
        if v is None:
            return None
        try:
            return json.loads(v)
        except (json.JSONDecodeError, TypeError):
            return None


class FileCacheQueryParam(SchemaBase):
    """文件缓存查询参数"""
    
    drive_account_id: int | None = Field(None, description="网盘账户ID")
    file_path: str | None = Field(None, description="文件路径")
    parent_id: str | None = Field(None, description="父目录ID")
    is_folder: bool | None = Field(None, description="是否为文件夹")
    is_valid: bool | None = Field(None, description="缓存是否有效")
    cache_version: str | None = Field(None, description="缓存版本")


class BatchCreateFileCacheParam(SchemaBase):
    """批量创建文件缓存参数"""
    
    drive_account_id: int = Field(..., description="网盘账户ID")
    files: list[dict[str, Any]] = Field(..., description="文件列表")
    cache_version: str | None = Field(None, description="缓存版本")
    
    @field_validator('files')
    @classmethod
    def validate_files(cls, v: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """验证文件列表"""
        if not v:
            raise ValueError("文件列表不能为空")
        
        required_fields = ['file_id', 'file_name', 'file_path']
        for file_info in v:
            for field in required_fields:
                if field not in file_info:
                    raise ValueError(f"文件信息缺少必需字段: {field}")
        
        return v


class FileCacheStatsParam(SchemaBase):
    """文件缓存统计参数"""
    
    drive_account_id: int | None = Field(None, description="网盘账户ID")


class GetFileCacheStats(SchemaBase):
    """文件缓存统计信息"""
    
    total_files: int = Field(..., description="总文件数")
    total_folders: int = Field(..., description="总文件夹数")
    total_size: int = Field(..., description="总文件大小")
    valid_caches: int = Field(..., description="有效缓存数")
    invalid_caches: int = Field(..., description="无效缓存数")
    cache_versions: list[str] = Field(..., description="缓存版本列表") 