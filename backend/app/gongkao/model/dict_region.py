#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class GkDictRegion(Base):
    """地区字典表（省市县三级）"""

    __tablename__ = 'gk_dict_region'
    __table_args__ = (
        sa.Index('ix_dict_region_parent', 'parent_code'),
        sa.Index('ix_dict_region_level', 'level'),
        {'comment': '地区字典表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)

    # 基础信息
    code: Mapped[str] = mapped_column(sa.String(20), unique=True, index=True, comment='地区代码')
    name: Mapped[str] = mapped_column(sa.String(100), index=True, comment='地区名称')
    level: Mapped[int] = mapped_column(sa.Integer, comment='级别: 1省 2市 3县/区')
    short_name: Mapped[str | None] = mapped_column(sa.String(50), default=None, comment='简称')
    parent_code: Mapped[str | None] = mapped_column(sa.String(20), default=None, comment='父级代码')

    # 扩展信息
    longitude: Mapped[float | None] = mapped_column(sa.Float, default=None, comment='经度')
    latitude: Mapped[float | None] = mapped_column(sa.Float, default=None, comment='纬度')
    is_remote_area: Mapped[bool] = mapped_column(sa.Boolean, default=False, comment='是否艰苦边远地区')
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='排序')
