#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.gongkao.model.hanyu import GkHanyu
from backend.common.model import Base, UserMixin, id_key


class GkHanyuGroup(Base, UserMixin):
    """汉语词语/成语辨析组主表"""

    __tablename__ = 'gk_hanyu_group'
    __table_args__ = (
        sa.Index('ix_gk_hanyu_group_category', 'category'),
        sa.Index('ix_gk_hanyu_group_group_no', 'group_no'),
        {'comment': '汉语词语/成语辨析组表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    title: Mapped[str] = mapped_column(sa.String(128), comment='辨析组标题(如: 阻碍 阻拦 阻止)')
    group_no: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='序号/题号(如: 398)')
    category: Mapped[str] = mapped_column(sa.String(50), default='实词辨析', comment='分类(如: 实词辨析、成语辨析)')
    summary: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='辨析概要与核心差异解析')
    example: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='典型例句/考题')
    sort_order: Mapped[int] = mapped_column(default=0, comment='排序')

    # 关联成员明细
    items: Mapped[list[GkHanyuGroupItem]] = relationship(
        init=False,
        back_populates='group',
        cascade='all, delete-orphan',
        order_by='GkHanyuGroupItem.sort_order',
        lazy='selectin',
    )


class GkHanyuGroupItem(Base):
    """汉语辨析组成员明细表"""

    __tablename__ = 'gk_hanyu_group_item'
    __table_args__ = (
        sa.Index('ix_gk_hanyu_group_item_group_id', 'group_id'),
        sa.Index('ix_gk_hanyu_group_item_hanyu_id', 'hanyu_id'),
        sa.Index('ix_gk_hanyu_group_item_word', 'word'),
        {'comment': '汉语辨析组成员明细表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    group_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey('gk_hanyu_group.id', ondelete='CASCADE'), comment='所属辨析组 ID'
    )
    word: Mapped[str] = mapped_column(sa.String(64), comment='词语名称')
    hanyu_id: Mapped[int | None] = mapped_column(
        sa.BigInteger, sa.ForeignKey('gk_hanyu.id', ondelete='SET NULL'), default=None, comment='关联汉语词汇 ID'
    )
    emphasis: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='对比侧重点/释义')
    collocation: Mapped[str | None] = mapped_column(sa.String(255), default=None, comment='常见搭配/适用对象')
    sort_order: Mapped[int] = mapped_column(default=0, comment='组内排序')

    # 关系属性
    group: Mapped[GkHanyuGroup] = relationship(init=False, back_populates='items')
    hanyu: Mapped[GkHanyu | None] = relationship(init=False, foreign_keys=[hanyu_id], lazy='joined')
