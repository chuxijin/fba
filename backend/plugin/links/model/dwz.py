#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UserMixin, id_key


class Dwz(Base, UserMixin):
    """短网址表"""

    __tablename__ = 'links_dwz'
    __table_args__ = (
        sa.Index('idx_links_dwz_code', 'code'),
        sa.Index('idx_links_dwz_status', 'status'),
        {'comment': '短网址表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    code: Mapped[str] = mapped_column(sa.String(16), unique=True, index=True, comment='短网址Key')
    original_url: Mapped[str] = mapped_column(sa.String(2048), comment='原网址')
    title: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='标题')
    remark: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='备注')
    clicks: Mapped[int] = mapped_column(default=0, comment='访问量')
    status: Mapped[int] = mapped_column(sa.SmallInteger, default=1, index=True, comment='状态(0停用 1启用)')
    entry_domain: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='入口域名')
    redirect_domain: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='中转域名')
    landing_domain: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='落地域名')
    domain_status: Mapped[int] = mapped_column(sa.SmallInteger, default=1, comment='域名状态(0异常 1正常)')
