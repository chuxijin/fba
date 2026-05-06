#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, UserMixin, id_key


class Qun(Base, UserMixin):
    """群活码表"""

    __tablename__ = 'links_qun'
    __table_args__ = (
        sa.Index('idx_links_qun_code', 'code'),
        sa.Index('idx_links_qun_status', 'status'),
        {'comment': '群活码表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    code: Mapped[str] = mapped_column(sa.String(16), unique=True, index=True, comment='活码Key')
    title: Mapped[str] = mapped_column(sa.String(128), comment='标题')
    remark: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='备注')
    clicks: Mapped[int] = mapped_column(default=0, comment='访问量')
    status: Mapped[int] = mapped_column(sa.SmallInteger, default=1, index=True, comment='状态(0停用 1启用)')
    entry_domain: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='入口域名')
    redirect_domain: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='中转域名')
    landing_domain: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='落地域名')
    domain_status: Mapped[int] = mapped_column(sa.SmallInteger, default=1, comment='域名状态(0异常 1正常)')
    kf: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='关联客服ID')
    kf_status: Mapped[int] = mapped_column(sa.SmallInteger, default=0, comment='客服状态(0不显示 1显示)')

    # 群二维码列表关系
    items: Mapped[list[QunItem]] = relationship(
        init=False, back_populates='qun', cascade='all, delete-orphan', lazy='selectin'
    )


class QunItem(Base, UserMixin):
    """群活码子表"""

    __tablename__ = 'links_qun_item'
    __table_args__ = (
        sa.Index('idx_links_qun_item_qun_id', 'qun_id'),
        sa.Index('idx_links_qun_item_status', 'status'),
        {'comment': '群活码子表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    qun_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('links_qun.id', ondelete='CASCADE'),
        comment='群活码ID',
    )
    qrcode: Mapped[str] = mapped_column(sa.String(512), comment='群二维码图片URL')
    limit: Mapped[int] = mapped_column(default=200, comment='扫码阈值')
    clicks: Mapped[int] = mapped_column(default=0, comment='访问量')
    longpress: Mapped[int] = mapped_column(default=0, comment='长按次数')
    leader: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='群主')
    status: Mapped[int] = mapped_column(
        sa.SmallInteger, default=1, index=True, comment='状态(0停用 1启用 2已满)'
    )

    # 关系
    qun: Mapped[Qun] = relationship(init=False, back_populates='items')
