#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class SysCatSchemaBase(SchemaBase):
    """分类基础"""

    name: str = Field(description='分类名称', min_length=1, max_length=50)
    color: str | None = Field(None, description='分类颜色')
    icon: str | None = Field(None, description='分类图标')
    app_code: str = Field(description='应用标识')
    user_id: int | None = Field(None, description='用户 ID（为空则为系统分类）')
    sort_order: int = Field(default=0, description='排序权重')
    status: bool = Field(default=True, description='状态')
    remark: str | None = Field(None, description='备注')


class CreateSysCatParam(SysCatSchemaBase):
    """创建分类参数"""

    parent_id: int | None = Field(None, description='父分类 ID')


class UpdateSysCatParam(SchemaBase):
    """更新分类参数"""

    name: str | None = Field(None, description='分类名称', min_length=1, max_length=50)
    color: str | None = Field(None, description='分类颜色')
    icon: str | None = Field(None, description='分类图标')
    parent_id: int | None = Field(None, description='父分类 ID')
    sort_order: int | None = Field(None, description='排序权重')
    status: bool | None = Field(None, description='状态')
    remark: str | None = Field(None, description='备注')


class GetSysCatDetail(SysCatSchemaBase):
    """分类详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='分类 ID')
    parent_id: int | None = Field(None, description='父分类 ID')
    level: int = Field(description='层级')
    path: str | None = Field(None, description='物化路径')
    created_by: int = Field(description='创建者')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetSysCatTree(GetSysCatDetail):
    """分类树"""

    children: list['GetSysCatTree'] | None = Field(None, description='子分类')


class SysCatTargetSchemaBase(SchemaBase):
    """分类关联基础"""

    cat_id: int = Field(description='分类 ID')
    target_type: str = Field(description='关联目标类型')
    target_id: int = Field(description='关联目标 ID')


class CreateSysCatTargetParam(SysCatTargetSchemaBase):
    """创建分类关联参数"""


class BatchBindCatsParam(SchemaBase):
    """批量绑定分类参数"""

    cat_ids: list[int] = Field(description='分类 ID 列表')
    target_type: str = Field(description='关联目标类型')
    target_id: int = Field(description='关联目标 ID')


class GetSysCatTargetDetail(SysCatTargetSchemaBase):
    """分类关联详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='关联 ID')
    created_by: int = Field(description='创建者')
    created_time: datetime = Field(description='创建时间')


class GetSysCatTargetWithCat(GetSysCatTargetDetail):
    """分类关联详情（含分类信息）"""

    cat_name: str = Field(description='分类名称')
    cat_color: str | None = Field(None, description='分类颜色')
    cat_icon: str | None = Field(None, description='分类图标')
    cat_path: str | None = Field(None, description='分类路径')
