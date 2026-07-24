#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UserMixin, id_key


class StudySpatialCubePattern(Base, UserMixin):
    """六面体面素材表"""

    __tablename__ = 'study_spatial_cube_pattern'
    __table_args__ = (
        sa.CheckConstraint("render_type IN ('builtin','image')", name='ck_study_spatial_cube_pattern_render_type'),
        sa.CheckConstraint(
            'rotation_period IN (90, 180, 360)',
            name='ck_study_spatial_cube_pattern_rotation_period',
        ),
        sa.Index('idx_study_spatial_cube_pattern_active_sort', 'is_active', 'sort'),
        {'comment': '六面体面素材表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    code: Mapped[str] = mapped_column(sa.String(64), unique=True, index=True, comment='素材编码')
    name: Mapped[str] = mapped_column(sa.String(64), comment='素材名称')
    render_type: Mapped[str] = mapped_column(sa.String(16), default='builtin', comment='渲染类型')
    asset_url: Mapped[str | None] = mapped_column(sa.String(1024), default=None, comment='远程素材 URL')
    asset_version: Mapped[str] = mapped_column(sa.String(64), default='1', comment='素材版本')
    rotation_period: Mapped[int] = mapped_column(sa.SmallInteger, default=360, comment='旋转等价周期')
    sort: Mapped[int] = mapped_column(sa.Integer, default=0, comment='排序')
    is_active: Mapped[bool] = mapped_column(default=True, comment='是否启用')
