#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class FoodSchemaBase(SchemaBase):
    """食物基础 Schema"""

    # === 基本信息 ===
    name: str = Field(description='食物名称')
    alias: str | None = Field(None, description='别名，逗号分隔')
    description: str | None = Field(None, description='描述')
    category_id: int | None = Field(None, description='分类ID')
    image_path: str | None = Field(None, description='图片路径')
    barcode: str | None = Field(None, description='条形码')

    # === 规格信息 ===
    serving_size: float = Field(default=100.0, description='份量大小(如100, 30)')
    serving_unit: str = Field(default='g', description='份量单位(g/ml)')

    # === 营养素（每100克）===
    energy: float | None = Field(None, description='能量(kcal)')
    protein: float | None = Field(None, description='蛋白质(g)')
    carbohydrate: float | None = Field(None, description='碳水化合物(g)')
    fat: float | None = Field(None, description='脂肪(g)')
    water: float | None = Field(None, description='水分(g)')
    fiber: float | None = Field(None, description='膳食纤维(g)')
    ash: float | None = Field(None, description='灰分(g)')

    # 维生素
    vitamin_a: float | None = Field(None, description='VA(μg)')
    carotene: float | None = Field(None, description='胡萝卜素(μg)')
    retinol_eq: float | None = Field(None, description='视黄醇当量(μg)')
    vitamin_b1: float | None = Field(None, description='VB1(mg)')
    vitamin_b2: float | None = Field(None, description='VB2(mg)')
    niacin: float | None = Field(None, description='烟酸(mg)')
    vitamin_c: float | None = Field(None, description='VC(mg)')
    vitamin_e: float | None = Field(None, description='VE(mg)')

    # 矿物质
    potassium: float | None = Field(None, description='钾(mg)')
    sodium: float | None = Field(None, description='钠(mg)')
    calcium: float | None = Field(None, description='钙(mg)')
    magnesium: float | None = Field(None, description='镁(mg)')
    iron: float | None = Field(None, description='铁(mg)')
    manganese: float | None = Field(None, description='锰(mg)')
    zinc: float | None = Field(None, description='锌(mg)')
    copper: float | None = Field(None, description='铜(mg)')
    phosphorus: float | None = Field(None, description='磷(mg)')
    selenium: float | None = Field(None, description='硒(μg)')

    # === 其他 ===
    source: str = Field(default='system', description='来源: system/user')
    status: bool = Field(default=True, description='状态')


class CreateFoodParam(FoodSchemaBase):
    """创建食物参数"""
    pass


class UpdateFoodParam(SchemaBase):
    """更新食物参数"""

    name: str | None = Field(None, description='食物名称')
    alias: str | None = Field(None, description='别名，逗号分隔')
    description: str | None = Field(None, description='描述')
    category_id: int | None = Field(None, description='分类ID')
    image_path: str | None = Field(None, description='图片路径')
    barcode: str | None = Field(None, description='条形码')

    serving_size: float | None = Field(None, description='份量大小(如100, 30)')
    serving_unit: str | None = Field(None, description='份量单位(g/ml)')

    energy: float | None = Field(None, description='能量(kcal)')
    protein: float | None = Field(None, description='蛋白质(g)')
    carbohydrate: float | None = Field(None, description='碳水化合物(g)')
    fat: float | None = Field(None, description='脂肪(g)')
    water: float | None = Field(None, description='水分(g)')
    fiber: float | None = Field(None, description='膳食纤维(g)')
    ash: float | None = Field(None, description='灰分(g)')

    vitamin_a: float | None = Field(None, description='VA(μg)')
    carotene: float | None = Field(None, description='胡萝卜素(μg)')
    retinol_eq: float | None = Field(None, description='视黄醇当量(μg)')
    vitamin_b1: float | None = Field(None, description='VB1(mg)')
    vitamin_b2: float | None = Field(None, description='VB2(mg)')
    niacin: float | None = Field(None, description='烟酸(mg)')
    vitamin_c: float | None = Field(None, description='VC(mg)')
    vitamin_e: float | None = Field(None, description='VE(mg)')

    potassium: float | None = Field(None, description='钾(mg)')
    sodium: float | None = Field(None, description='钠(mg)')
    calcium: float | None = Field(None, description='钙(mg)')
    magnesium: float | None = Field(None, description='镁(mg)')
    iron: float | None = Field(None, description='铁(mg)')
    manganese: float | None = Field(None, description='锰(mg)')
    zinc: float | None = Field(None, description='锌(mg)')
    copper: float | None = Field(None, description='铜(mg)')
    phosphorus: float | None = Field(None, description='磷(mg)')
    selenium: float | None = Field(None, description='硒(μg)')

    source: str | None = Field(None, description='来源: system/user')
    status: bool | None = Field(None, description='状态')


class GetFoodDetail(FoodSchemaBase):
    """食物详情"""
    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='ID')
    created_by: int | None = Field(None, description='创建者')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
