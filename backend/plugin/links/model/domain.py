#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UserMixin, id_key


class Domain(Base, UserMixin):
    """域名表"""

    __tablename__ = 'links_domain'
    __table_args__ = (
        sa.Index('idx_links_domain_type', 'domain_type'),
        sa.UniqueConstraint('domain', 'domain_type', name='uq_links_domain_type'),
        {'comment': '域名表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    domain: Mapped[str] = mapped_column(sa.String(128), index=True, comment='域名')
    domain_type: Mapped[int] = mapped_column(
        sa.SmallInteger, comment='域名类型(1入口域名 2中转域名 3落地域名)'
    )
    remark: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='备注')
