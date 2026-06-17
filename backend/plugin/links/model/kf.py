#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, UserMixin, id_key


class Kf(Base, UserMixin):
    """客服码表"""

    __tablename__ = 'links_kf'
    __table_args__ = (
        sa.Index('idx_links_kf_code', 'code'),
        sa.Index('idx_links_kf_status', 'status'),
        {'comment': '客服码表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    code: Mapped[str] = mapped_column(sa.String(16), unique=True, index=True, comment='客服码Key')
    title: Mapped[str] = mapped_column(sa.String(128), comment='标题')
    remark: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='备注')
    clicks: Mapped[int] = mapped_column(default=0, comment='访问量')
    status: Mapped[int] = mapped_column(sa.SmallInteger, default=1, index=True, comment='状态(0停用 1启用)')
    online: Mapped[str | None] = mapped_column(sa.String(1024), default=None, comment='在线规则(JSON)')
    entry_domain: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='入口域名')
    redirect_domain: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='中转域名')
    landing_domain: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='落地域名')
    domain_status: Mapped[int] = mapped_column(sa.SmallInteger, default=1, comment='域名状态(0异常 1正常)')

    # 客服二维码列表关系
    items: Mapped[list[KfItem]] = relationship(
        init=False, back_populates='kf', cascade='all, delete-orphan', lazy='selectin'
    )


class KfItem(Base, UserMixin):
    """客服码子表"""

    __tablename__ = 'links_kf_item'
    __table_args__ = (
        sa.Index('idx_links_kf_item_kf_id', 'kf_id'),
        sa.Index('idx_links_kf_item_status', 'status'),
        {'comment': '客服码子表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    kf_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('links_kf.id', ondelete='CASCADE'),
        comment='客服码ID',
    )
    qrcode: Mapped[str] = mapped_column(sa.String(512), comment='客服二维码图片URL')
    limit: Mapped[int] = mapped_column(default=200, comment='扫码阈值')
    clicks: Mapped[int] = mapped_column(default=0, comment='访问量')
    longpress: Mapped[int] = mapped_column(default=0, comment='长按次数')
    leader: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='客服名称')
    status: Mapped[int] = mapped_column(sa.SmallInteger, default=1, index=True, comment='状态(0停用 1启用 2已满)')

    # 关系
    kf: Mapped[Kf] = relationship(init=False, back_populates='items')
