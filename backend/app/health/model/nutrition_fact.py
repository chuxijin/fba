#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class NutritionFact(Base):
    """营养成分表"""

    __tablename__ = 'health_nutrition_fact'

    id: Mapped[id_key] = mapped_column(init=False)
    food_id: Mapped[int] = mapped_column(sa.BigInteger, unique=True, index=True, comment='食物 ID')
    reference_amount: Mapped[float] = mapped_column(sa.Numeric(10, 2), default=100, comment='参考份量')
    reference_unit: Mapped[str] = mapped_column(sa.String(16), default='g', comment='参考单位')
    calories: Mapped[float | None] = mapped_column(sa.Numeric(10, 2), default=None, comment='热量(kcal)')
    protein: Mapped[float | None] = mapped_column(sa.Numeric(10, 2), default=None, comment='蛋白质(g)')
    fat: Mapped[float | None] = mapped_column(sa.Numeric(10, 2), default=None, comment='脂肪(g)')
    carbohydrate: Mapped[float | None] = mapped_column(sa.Numeric(10, 2), default=None, comment='碳水化合物(g)')
    saturated_fat: Mapped[float | None] = mapped_column(sa.Numeric(10, 2), default=None, comment='饱和脂肪(g)')
    unsaturated_fat: Mapped[float | None] = mapped_column(sa.Numeric(10, 2), default=None, comment='不饱和脂肪(g)')
    dietary_fiber: Mapped[float | None] = mapped_column(sa.Numeric(10, 2), default=None, comment='膳食纤维(g)')
    sugar: Mapped[float | None] = mapped_column(sa.Numeric(10, 2), default=None, comment='糖(g)')
    sodium: Mapped[float | None] = mapped_column(sa.Numeric(10, 2), default=None, comment='钠(mg)')
    cholesterol: Mapped[float | None] = mapped_column(sa.Numeric(10, 2), default=None, comment='胆固醇(mg)')
    calcium: Mapped[float | None] = mapped_column(sa.Numeric(10, 2), default=None, comment='钙(mg)')
    iron: Mapped[float | None] = mapped_column(sa.Numeric(10, 2), default=None, comment='铁(mg)')
    vitamin_c: Mapped[float | None] = mapped_column(sa.Numeric(10, 2), default=None, comment='维生素 C(mg)')
    vitamin_d: Mapped[float | None] = mapped_column(sa.Numeric(10, 2), default=None, comment='维生素 D(μg)')
    water: Mapped[float | None] = mapped_column(sa.Numeric(10, 2), default=None, comment='水分(g)')
    gi_value: Mapped[int | None] = mapped_column(sa.SmallInteger, default=None, comment='升糖指数 GI 值')
