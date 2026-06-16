#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UserMixin, id_key


class Log(Base, UserMixin):
    """通用访问日志表"""

    __tablename__ = 'links_log'
    __table_args__ = (
        sa.Index('idx_links_log_type_target', 'type', 'target_id'),
        sa.Index('idx_links_log_device', 'device'),
        sa.Index('idx_links_log_created', 'created_time'),
        {'comment': '通用访问日志表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    type: Mapped[int] = mapped_column(sa.SmallInteger, comment='类型(1短链 2群活码 3客服码 4静态页面)')
    target_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='目标ID')
    ip: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='访问IP')
    device: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='设备(Android/iOS/Windows/Mac/iPad)')
    reference: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='来源(微信/PC浏览器/手机浏览器)')
    user_agent: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='浏览器UA')
    country: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='国家')
    city: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='城市')
    pv: Mapped[int] = mapped_column(default=1, comment='访问次数')
