#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""资料模型"""
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class GkResource(Base):
    """资料表"""

    __tablename__ = 'gk_resource'

    id: Mapped[id_key] = mapped_column(init=False)
    title: Mapped[str] = mapped_column(sa.String(255), comment='标题')
    category: Mapped[str] = mapped_column(sa.String(50), index=True, comment='分类：行测/申论/面试/备考')
    description: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='描述')
    file_path: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='本地文件路径')
    link: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='外部链接')
    file_type: Mapped[str | None] = mapped_column(sa.String(20), default=None, comment='文件类型：pdf/doc/video/link')
    view_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='查看次数')
    sort_order: Mapped[int] = mapped_column(sa.Integer, default=0, comment='排序')
    status: Mapped[bool] = mapped_column(sa.Boolean, default=True, comment='状态')
