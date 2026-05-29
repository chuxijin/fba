#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class BankMountSchemaBase(SchemaBase):
    """挂载基础"""

    collection_id: int = Field(gt=0, description='合集 ID')
    item_id: int = Field(gt=0, description='被挂载内容 ID')
    sort_order: int = Field(default=0, description='排序权重')
    status: int = Field(default=1, ge=0, description='状态')


class CreateBankMountParam(BankMountSchemaBase):
    """创建挂载参数"""


class UpdateBankMountParam(SchemaBase):
    """更新挂载参数"""

    collection_id: int | None = Field(None, gt=0, description='合集 ID')
    item_id: int | None = Field(None, gt=0, description='被挂载内容 ID')
    sort_order: int | None = Field(None, description='排序权重')
    status: int | None = Field(None, ge=0, description='状态')


class DeleteBankMountParam(SchemaBase):
    """删除挂载参数"""

    ids: list[int] = Field(description='挂载 ID 列表')


class GetBankMountDetail(BankMountSchemaBase):
    """挂载详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='挂载 ID')
    collection_name: str | None = Field(None, description='合集名称')
    item_name: str | None = Field(None, description='内容名称')
    item_bank_type: int | None = Field(None, description='内容类型: 1=习题, 2=试卷, 3=合集')
    created_by: int = Field(description='创建者')
    updated_by: int | None = Field(None, description='修改者')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
