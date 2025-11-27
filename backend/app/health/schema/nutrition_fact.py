#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class NutritionFactSchemaBase(SchemaBase):
    """营养成分基础模型"""

    food_id: int = Field(description='食物 ID')
    reference_amount: float = Field(100, ge=0, description='参考份量')
    reference_unit: str = Field('g', description='参考单位')
    calories: float | None = Field(None, ge=0, description='热量(kcal)')
    protein: float | None = Field(None, ge=0, description='蛋白质(g)')
    fat: float | None = Field(None, ge=0, description='脂肪(g)')
    carbohydrate: float | None = Field(None, ge=0, description='碳水化合物(g)')
    saturated_fat: float | None = Field(None, ge=0, description='饱和脂肪(g)')
    unsaturated_fat: float | None = Field(None, ge=0, description='不饱和脂肪(g)')
    dietary_fiber: float | None = Field(None, ge=0, description='膳食纤维(g)')
    sugar: float | None = Field(None, ge=0, description='糖(g)')
    sodium: float | None = Field(None, ge=0, description='钠(mg)')
    cholesterol: float | None = Field(None, ge=0, description='胆固醇(mg)')
    calcium: float | None = Field(None, ge=0, description='钙(mg)')
    iron: float | None = Field(None, ge=0, description='铁(mg)')
    vitamin_c: float | None = Field(None, ge=0, description='维生素 C(mg)')
    vitamin_d: float | None = Field(None, ge=0, description='维生素 D(μg)')
    water: float | None = Field(None, ge=0, description='水分(g)')
    gi_value: int | None = Field(None, ge=0, le=100, description='升糖指数 GI 值')


class CreateNutritionFactParam(NutritionFactSchemaBase):
    """创建营养成分参数"""


class UpdateNutritionFactParam(NutritionFactSchemaBase):
    """更新营养成分参数"""


class GetNutritionFactDetail(NutritionFactSchemaBase):
    """营养成分详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='营养成分 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
