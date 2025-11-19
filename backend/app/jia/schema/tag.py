#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class TagSchemaBase(SchemaBase):
    """标签基础"""

    name: str = Field(description='标签名称')
    color: str | None = Field(None, description='标签颜色')


class CreateTagParam(TagSchemaBase):
    """创建标签参数"""


class UpdateTagParam(SchemaBase):
    """更新标签参数"""

    name: str | None = Field(None, description='标签名称')
    color: str | None = Field(None, description='标签颜色')


class DeleteTagParam(SchemaBase):
    """删除标签参数"""

    pks: list[int] = Field(description='标签 ID 列表')


class GetTagDetail(TagSchemaBase):
    """标签详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='标签 ID')
    server_id: str | None = Field(None, description='服务器 ID')
    sync_status: str = Field(description='同步状态')
    last_synced_at: int | None = Field(None, description='最后同步时间戳')
    version: int = Field(description='版本号')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
    created_by: int = Field(description='创建者')
    updated_by: int | None = Field(None, description='更新者')
    deleted_at: int | None = Field(None, description='软删除时间戳')

