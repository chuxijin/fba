#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class FoodTag(Base):
    """食物标签表"""

    __tablename__ = 'health_food_tag'

    id: Mapped[id_key] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(sa.String(64), unique=True, comment='标签名称')
    tag_group: Mapped[int] = mapped_column(default=0, comment='标签分组(0健康属性 1饮食偏好 2特殊认证)')
    color: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='标签颜色')
    icon: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='标签图标')
    sort: Mapped[int] = mapped_column(default=0, comment='排序')
    status: Mapped[int] = mapped_column(default=1, comment='状态(0停用 1正常)')
    del_flag: Mapped[bool] = mapped_column(default=False, comment='删除标志(0删除 1存在)')
