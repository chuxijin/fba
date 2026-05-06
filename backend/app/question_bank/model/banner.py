#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class Banner(Base):
    """轮播图表"""

    __tablename__ = 'study_banner'
    __table_args__ = (
        sa.Index('idx_study_banner_status_scene_sort', 'status', 'scene', 'sort'),
        {'comment': '轮播图表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    title: Mapped[str] = mapped_column(sa.String(100), comment='标题')
    image_url: Mapped[str] = mapped_column(sa.String(500), comment='图片 URL')
    link_type: Mapped[str] = mapped_column(
        sa.String(20),
        default='none',
        comment='链接类型: none/url/miniprogram',
    )
    link_url: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='跳转链接')
    scene: Mapped[str] = mapped_column(sa.String(50), default='home', comment='展示场景: home/practice/study 等')
    sort: Mapped[int] = mapped_column(sa.Integer, default=0, comment='排序（数字越小越靠前）')
    status: Mapped[int] = mapped_column(sa.SmallInteger, default=1, index=True, comment='状态: 0=禁用, 1=启用')
    start_time: Mapped[datetime | None] = mapped_column(default=None, comment='开始时间')
    end_time: Mapped[datetime | None] = mapped_column(default=None, comment='结束时间')
    click_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='点击次数')
