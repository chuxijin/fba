#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from decimal import Decimal

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class BankSchemaBase(SchemaBase):
    """题库基础"""

    cat_id: int = Field(description='所属分类 ID')
    name: str = Field(description='题库名称')
    code: str = Field(description='题库编码')
    desc: str | None = Field(None, description='题库描述')
    cover_url: str | None = Field(None, description='封面地址')
    diff_id: int | None = Field(None, description='难度字典 ID')
    parent_id: int | None = Field(None, description='父级题库 ID')
    status: int = Field(default=1, description='题库状态')
    scope: int = Field(default=1, description='可见范围')


class GetBankDetail(BankSchemaBase):
    """题库详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='题库 ID')
    q_count: int = Field(description='题目数量')
    total_score: Decimal = Field(description='题库总分')
    buy_count: int = Field(description='购买数量')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetBankWithRelationDetail(GetBankDetail):
    """题库关联详情"""

    model_config = ConfigDict(from_attributes=True)

    category: dict | None = Field(None, description='分类信息')


class BankParam(SchemaBase):
    """题库参数"""

    cat_id: int | None = Field(None, description='分类 ID')
    status: int | None = Field(None, description='题库状态')
    scope: int | None = Field(None, description='可见范围')
    keyword: str | None = Field(None, description='关键字搜索（名称/编码）')


class CreateBankParam(BankSchemaBase):
    """创建题库参数"""


class UpdateBankParam(BankSchemaBase):
    """更新题库参数"""


class DeleteBankParam(SchemaBase):
    """删除题库参数"""

    ids: list[int] = Field(description='题库 ID 列表')
