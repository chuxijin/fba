#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, UserMixin, id_key


class JiaCategory(Base, UserMixin):
    """分类表"""

    __tablename__ = 'jia_category'

    id: Mapped[id_key] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(String(255), comment='分类名称')
    server_id: Mapped[str | None] = mapped_column(String(100), default=None, index=True, comment='服务器ID')
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey('jia_category.id', ondelete='CASCADE'),
        default=None,
        index=True,
        comment='父级分类ID',
    )
    parent_server_id: Mapped[str | None] = mapped_column(String(100), default=None, comment='父级分类服务器ID')
    icon: Mapped[str | None] = mapped_column(String(100), default=None, comment='分类图标')
    color: Mapped[str | None] = mapped_column(String(50), default=None, comment='分类颜色')
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment='排序顺序')
    sync_status: Mapped[str] = mapped_column(
        String(20),
        default='synced',
        index=True,
        comment='同步状态: synced/pending/conflict/failed',
    )
    last_synced_at: Mapped[int | None] = mapped_column(BigInteger, default=None, comment='最后同步时间戳')
    version: Mapped[int] = mapped_column(Integer, default=1, comment='版本号')
    deleted_at: Mapped[int | None] = mapped_column(BigInteger, default=None, index=True, comment='软删除时间戳')

    # 自引用关系
    children: Mapped[list['JiaCategory']] = relationship(
        init=False,
        back_populates='parent',
        cascade='all, delete-orphan',
        foreign_keys=[parent_id],
    )
    parent: Mapped['JiaCategory | None'] = relationship(
        init=False,
        back_populates='children',
        remote_side=[id],
        foreign_keys=[parent_id],
    )

