#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date
from decimal import Decimal

from pydantic import Field

from backend.common.schema import SchemaBase


class ItemSchemaBase(SchemaBase):
    """物品基础模型"""

    name: str = Field(description='物品名称')
    category: str | None = Field(None, description='分类')
    quantity: int = Field(default=1, ge=0, description='当前数量')
    standard_quantity: int = Field(default=1, ge=1, description='标准数量')
    consume_days: int | None = Field(None, ge=1, description='消耗周期(天)')
    expire_date: date | None = Field(None, description='保质期(到期日期)')
    description: str | None = Field(None, description='描述')
    location: str | None = Field(None, description='存放位置')
    acquired_date: str | None = Field(None, description='购入日期')
    price: Decimal | None = Field(None, ge=0, description='价格')
    disposal_method: str | None = Field(None, description='处置方式')
    image_path: str | None = Field(None, description='图片路径')
    notes: str | None = Field(None, description='备注')


class CreateItemParam(ItemSchemaBase):
    """创建物品参数"""

    pass


class UpdateItemParam(SchemaBase):
    """更新物品参数"""

    name: str | None = Field(None, description='物品名称')
    category: str | None = Field(None, description='分类')
    quantity: int | None = Field(None, ge=0, description='当前数量')
    standard_quantity: int | None = Field(None, ge=1, description='标准数量')
    consume_days: int | None = Field(None, ge=1, description='消耗周期(天)')
    expire_date: date | None = Field(None, description='保质期(到期日期)')
    description: str | None = Field(None, description='描述')
    location: str | None = Field(None, description='存放位置')
    acquired_date: str | None = Field(None, description='购入日期')
    price: Decimal | None = Field(None, ge=0, description='价格')
    disposal_method: str | None = Field(None, description='处置方式')
    image_path: str | None = Field(None, description='图片路径')
    notes: str | None = Field(None, description='备注')


class GetItemDetail(ItemSchemaBase):
    """物品详情"""

    id: int = Field(description='物品 ID')
    status: str = Field(description='状态')
    created_by: int = Field(description='创建者')
    updated_by: int | None = Field(None, description='修改者')


class GetItemList(SchemaBase):
    """物品列表项"""

    id: int = Field(description='物品 ID')
    name: str = Field(description='物品名称')
    category: str | None = Field(None, description='分类')
    quantity: int = Field(description='当前数量')
    standard_quantity: int = Field(description='标准数量')
    status: str = Field(description='状态')
    location: str | None = Field(None, description='存放位置')
    expire_date: date | None = Field(None, description='保质期')
