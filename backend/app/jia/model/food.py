#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pgvector.sqlalchemy import Vector
from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UserMixin, id_key


class HealthyFood(Base, UserMixin):
    """食物营养数据表"""

    __tablename__ = 'jia_food'

    id: Mapped[id_key] = mapped_column(init=False)

    # === 基本信息 ===
    name: Mapped[str] = mapped_column(String(100), index=True, comment='食物名称')
    alias: Mapped[str | None] = mapped_column(String(200), default=None, comment='别名，逗号分隔')
    description: Mapped[str | None] = mapped_column(String(500), default=None, comment='描述')
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey('sys_category.id'), default=None, comment='分类ID'
    )
    image_path: Mapped[str | None] = mapped_column(String(255), default=None, comment='图片路径')
    barcode: Mapped[str | None] = mapped_column(String(50), index=True, default=None, comment='条形码')

    # === 规格信息 ===
    serving_size: Mapped[float] = mapped_column(
        Numeric(10, 2), default=100, comment='份量大小(如100, 30)'
    )
    serving_unit: Mapped[str] = mapped_column(
        String(20), default='g', comment='份量单位(g/ml)'
    )

    # === 营养素（每100克）===
    energy: Mapped[float | None] = mapped_column(Numeric(10, 2), default=None, comment='能量(kcal)')
    protein: Mapped[float | None] = mapped_column(Numeric(10, 2), default=None, comment='蛋白质(g)')
    carbohydrate: Mapped[float | None] = mapped_column(Numeric(10, 2), default=None, comment='碳水化合物(g)')
    fat: Mapped[float | None] = mapped_column(Numeric(10, 2), default=None, comment='脂肪(g)')
    water: Mapped[float | None] = mapped_column(Numeric(10, 2), default=None, comment='水分(g)')
    fiber: Mapped[float | None] = mapped_column(Numeric(10, 2), default=None, comment='膳食纤维(g)')
    ash: Mapped[float | None] = mapped_column(Numeric(10, 2), default=None, comment='灰分(g)')

    # 维生素
    vitamin_a: Mapped[float | None] = mapped_column(Numeric(10, 3), default=None, comment='VA(μg)')
    carotene: Mapped[float | None] = mapped_column(Numeric(10, 3), default=None, comment='胡萝卜素(μg)')
    retinol_eq: Mapped[float | None] = mapped_column(
        Numeric(10, 3), default=None, comment='视黄醇当量(μg)'
    )
    vitamin_b1: Mapped[float | None] = mapped_column(Numeric(10, 3), default=None, comment='VB1(mg)')
    vitamin_b2: Mapped[float | None] = mapped_column(Numeric(10, 3), default=None, comment='VB2(mg)')
    niacin: Mapped[float | None] = mapped_column(Numeric(10, 3), default=None, comment='烟酸(mg)')
    vitamin_c: Mapped[float | None] = mapped_column(Numeric(10, 3), default=None, comment='VC(mg)')
    vitamin_e: Mapped[float | None] = mapped_column(Numeric(10, 3), default=None, comment='VE(mg)')

    # 矿物质
    potassium: Mapped[float | None] = mapped_column(Numeric(10, 3), default=None, comment='钾(mg)')
    sodium: Mapped[float | None] = mapped_column(Numeric(10, 3), default=None, comment='钠(mg)')
    calcium: Mapped[float | None] = mapped_column(Numeric(10, 3), default=None, comment='钙(mg)')
    magnesium: Mapped[float | None] = mapped_column(Numeric(10, 3), default=None, comment='镁(mg)')
    iron: Mapped[float | None] = mapped_column(Numeric(10, 3), default=None, comment='铁(mg)')
    manganese: Mapped[float | None] = mapped_column(Numeric(10, 3), default=None, comment='锰(mg)')
    zinc: Mapped[float | None] = mapped_column(Numeric(10, 3), default=None, comment='锌(mg)')
    copper: Mapped[float | None] = mapped_column(Numeric(10, 3), default=None, comment='铜(mg)')
    phosphorus: Mapped[float | None] = mapped_column(Numeric(10, 3), default=None, comment='磷(mg)')
    selenium: Mapped[float | None] = mapped_column(Numeric(10, 3), default=None, comment='硒(μg)')

    # === 扩展字段 ===
    vector: Mapped[list[float] | None] = mapped_column(
        Vector(1536), default=None, deferred=True, comment='向量化数据(1536维，默认不加载)'
    )
    source: Mapped[str] = mapped_column(
        String(20), default='system', comment='来源: system/user'
    )
    status: Mapped[bool] = mapped_column(default=True, comment='状态')
