#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, UserMixin, id_key


class Note(Base, UserMixin):
    """笔记表"""

    __tablename__ = 'jia_note'

    id: Mapped[id_key] = mapped_column(init=False)
    type: Mapped[str] = mapped_column(String(20), index=True, comment='类型: folder 或 note')
    name: Mapped[str] = mapped_column(String(255), comment='名称')
    server_id: Mapped[str | None] = mapped_column(String(100), default=None, index=True, comment='服务器上的ID')
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey('jia_note.id', ondelete='CASCADE'),
        default=None,
        index=True,
        comment='父级ID',
    )
    parent_server_id: Mapped[str | None] = mapped_column(String(100), default=None, comment='父级服务器ID')
    category_ids: Mapped[str | None] = mapped_column(Text, default=None, comment='分类ID列表(JSON 数组)')
    tag_ids: Mapped[str | None] = mapped_column(Text, default=None, comment='标签ID列表(JSON 数组)')
    title: Mapped[str | None] = mapped_column(String(500), default=None, comment='笔记标题')
    content: Mapped[str | None] = mapped_column(Text, default=None, comment='内容(Delta JSON 格式)')
    icon: Mapped[str | None] = mapped_column(String(100), default=None, comment='图标')
    color: Mapped[str | None] = mapped_column(String(50), default=None, comment='颜色标记')
    sort_order: Mapped[int] = mapped_column(Integer, default=0, comment='排序顺序')
    is_pinned: Mapped[int] = mapped_column(Integer, default=0, comment='是否置顶(0/1)')
    is_favorite: Mapped[int] = mapped_column(Integer, default=0, comment='是否收藏(0/1)')
    word_count: Mapped[int] = mapped_column(Integer, default=0, comment='字数统计')
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
    children: Mapped[list['Note']] = relationship(
        init=False,
        back_populates='parent',
        cascade='all, delete-orphan',
        foreign_keys=[parent_id],
    )
    parent: Mapped['Note | None'] = relationship(
        init=False,
        back_populates='children',
        remote_side=[id],
        foreign_keys=[parent_id],
    )
