#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class Food(Base):
    """食物表"""

    __tablename__ = 'health_food'
    __table_args__ = (
        sa.Index('ix_health_food_fk_category_id', 'category_id'),
        {'comment': '食物表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(sa.String(128), index=True, comment='食物名称')
    category_id: Mapped[int] = mapped_column(sa.BigInteger, comment='分类 ID')
    name_en: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='英文名称')
    food_type: Mapped[int] = mapped_column(default=0, comment='食物类型(0原始食物 1加工食物)')
    processing_level: Mapped[int] = mapped_column(default=0, comment='加工程度(0未加工 1轻度加工 2中度加工 3深度加工)')
    image: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='食物图片 URL')
    serving_size: Mapped[float] = mapped_column(sa.Numeric(10, 2), default=100, comment='标准份量数值')
    serving_unit: Mapped[str] = mapped_column(sa.String(16), default='g', comment='份量单位')
    description: Mapped[str | None] = mapped_column(sa.String(1024), default=None, comment='食物描述')
    status: Mapped[int] = mapped_column(default=1, comment='状态(0下架 1上架)')
    del_flag: Mapped[bool] = mapped_column(default=False, comment='删除标志(0删除 1存在)')
