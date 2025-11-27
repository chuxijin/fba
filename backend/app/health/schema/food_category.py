#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.enums import StatusType
from backend.common.schema import SchemaBase


class FoodCategorySchemaBase(SchemaBase):
    """食物分类基础模型"""

    name: str = Field(description='分类名称')
    parent_id: int | None = Field(None, description='父分类 ID')
    sort: int = Field(0, ge=0, description='排序')
    icon: str | None = Field(None, description='分类图标')
    description: str | None = Field(None, description='分类描述')
    status: StatusType = Field(description='状态')


class CreateFoodCategoryParam(FoodCategorySchemaBase):
    """创建食物分类参数"""


class UpdateFoodCategoryParam(FoodCategorySchemaBase):
    """更新食物分类参数"""


class GetFoodCategoryDetail(FoodCategorySchemaBase):
    """食物分类详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='分类 ID')
    del_flag: bool = Field(description='是否删除')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetFoodCategoryTree(GetFoodCategoryDetail):
    """食物分类树"""

    children: list['GetFoodCategoryTree'] | None = Field(None, description='子分类')
