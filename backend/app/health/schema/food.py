#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.app.health.schema.enum import FoodType, ProcessingLevel
from backend.common.enums import StatusType
from backend.common.schema import SchemaBase


class FoodSchemaBase(SchemaBase):
    """食物基础模型"""

    name: str = Field(description='食物名称')
    name_en: str | None = Field(None, description='英文名称')
    category_id: int = Field(description='分类 ID')
    food_type: FoodType = Field(description='食物类型')
    processing_level: ProcessingLevel = Field(description='加工程度')
    image: str | None = Field(None, description='食物图片 URL')
    serving_size: float = Field(100, ge=0, description='标准份量数值')
    serving_unit: str = Field('g', description='份量单位')
    description: str | None = Field(None, description='食物描述')
    status: StatusType = Field(description='状态')


class CreateFoodParam(FoodSchemaBase):
    """创建食物参数"""


class UpdateFoodParam(FoodSchemaBase):
    """更新食物参数"""


class GetFoodDetail(FoodSchemaBase):
    """食物详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='食物 ID')
    del_flag: bool = Field(description='是否删除')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
