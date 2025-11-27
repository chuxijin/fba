#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.app.health.schema.enum import TagGroup
from backend.common.enums import StatusType
from backend.common.schema import SchemaBase


class FoodTagSchemaBase(SchemaBase):
    """食物标签基础模型"""

    name: str = Field(description='标签名称')
    tag_group: TagGroup = Field(description='标签分组')
    color: str | None = Field(None, description='标签颜色')
    icon: str | None = Field(None, description='标签图标')
    sort: int = Field(0, ge=0, description='排序')
    status: StatusType = Field(description='状态')


class CreateFoodTagParam(FoodTagSchemaBase):
    """创建食物标签参数"""


class UpdateFoodTagParam(FoodTagSchemaBase):
    """更新食物标签参数"""


class GetFoodTagDetail(FoodTagSchemaBase):
    """食物标签详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='标签 ID')
    del_flag: bool = Field(description='是否删除')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class AddFoodTagRelationParam(SchemaBase):
    """添加食物标签关联参数"""

    food_id: int = Field(description='食物 ID')
    tag_ids: list[int] = Field(description='标签 ID 列表')


class RemoveFoodTagRelationParam(SchemaBase):
    """移除食物标签关联参数"""

    food_id: int = Field(description='食物 ID')
    tag_ids: list[int] = Field(description='标签 ID 列表')
