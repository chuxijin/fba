#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class SysTagSchemaBase(SchemaBase):
    """标签基础"""

    name: str = Field(description='标签名称', min_length=1, max_length=50)
    color: str | None = Field(None, description='标签颜色')
    icon: str | None = Field(None, description='标签图标')
    app_code: str = Field(description='应用标识')
    user_id: int | None = Field(None, description='用户 ID（为空则为系统级标签）')
    sort_order: int = Field(default=0, description='排序权重')
    status: bool = Field(default=True, description='状态')
    remark: str | None = Field(None, description='备注')


class CreateSysTagParam(SysTagSchemaBase):
    """创建标签参数"""


class UpdateSysTagParam(SchemaBase):
    """更新标签参数"""

    name: str | None = Field(None, description='标签名称', min_length=1, max_length=50)
    color: str | None = Field(None, description='标签颜色')
    icon: str | None = Field(None, description='标签图标')
    sort_order: int | None = Field(None, description='排序权重')
    status: bool | None = Field(None, description='状态')
    remark: str | None = Field(None, description='备注')


class GetSysTagDetail(SysTagSchemaBase):
    """标签详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='标签 ID')
    created_by: int = Field(description='创建者')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetSysTagListItem(GetSysTagDetail):
    """标签列表项"""

    target_count: int = Field(default=0, description='关联目标数')


class SysTagTargetSchemaBase(SchemaBase):
    """标签关联基础"""

    tag_id: int = Field(description='标签 ID')
    target_type: str = Field(description='关联目标类型')
    target_id: int = Field(description='关联目标 ID')


class CreateSysTagTargetParam(SysTagTargetSchemaBase):
    """创建标签关联参数"""


class BatchBindTagsParam(SchemaBase):
    """批量绑定标签参数"""

    tag_ids: list[int] = Field(description='标签 ID 列表')
    target_type: str = Field(description='关联目标类型')
    target_id: int = Field(description='关联目标 ID')


class GetSysTagTargetDetail(SysTagTargetSchemaBase):
    """标签关联详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='关联 ID')
    created_by: int = Field(description='创建者')
    created_time: datetime = Field(description='创建时间')


class GetSysTagTargetWithTag(GetSysTagTargetDetail):
    """标签关联详情（含标签信息）"""

    tag_name: str = Field(description='标签名称')
    tag_color: str | None = Field(None, description='标签颜色')
    tag_icon: str | None = Field(None, description='标签图标')
