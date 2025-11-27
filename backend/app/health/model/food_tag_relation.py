#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, id_key
from backend.utils.timezone import timezone


class FoodTagRelation(Base):
    """食物标签关联表"""

    __tablename__ = 'health_food_tag_relation'
    __table_args__ = (
        sa.UniqueConstraint('food_id', 'tag_id', name='uk_food_tag'),
        {'comment': '食物标签关联表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    food_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='食物 ID')
    tag_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='标签 ID')
