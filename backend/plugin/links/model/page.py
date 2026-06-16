#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UniversalText, UserMixin, id_key


class Page(Base, UserMixin):
    """静态页面表"""

    __tablename__ = 'links_page'
    __table_args__ = (
        sa.Index('idx_links_page_code', 'code'),
        sa.Index('idx_links_page_status', 'status'),
        {'comment': '静态页面表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    code: Mapped[str] = mapped_column(sa.String(16), unique=True, index=True, comment='页面Key')
    title: Mapped[str] = mapped_column(sa.String(128), comment='标题')
    html_content: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='HTML 内容')
    remark: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='备注')
    clicks: Mapped[int] = mapped_column(default=0, comment='访问量')
    status: Mapped[int] = mapped_column(sa.SmallInteger, default=1, index=True, comment='状态(0停用 1启用)')
    entry_domain: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='入口域名')
    redirect_domain: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='中转域名')
    landing_domain: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='落地域名')
    domain_status: Mapped[int] = mapped_column(sa.SmallInteger, default=1, comment='域名状态(0异常 1正常)')
