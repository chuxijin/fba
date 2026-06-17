#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class VisitLog(Base):
    """访问日志表 - 记录每次访问"""

    __tablename__ = 'plugin_visit_log'
    __table_args__ = (
        sa.Index('idx_plugin_visit_log_date', 'visit_date'),
        sa.Index('idx_plugin_visit_log_ip', 'ip_address'),
        {'comment': '访问日志表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)

    # 访问信息
    ip_address: Mapped[str] = mapped_column(sa.String(50), comment='访问者IP')
    user_agent: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='浏览器UA')
    referer: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='来源页面')
    path: Mapped[str | None] = mapped_column(sa.String(255), default=None, comment='访问路径')

    # 日期（用于统计）
    visit_date: Mapped[date] = mapped_column(sa.Date, default_factory=date.today, comment='访问日期')


class VisitStats(Base):
    """访问统计表 - 按日汇总"""

    __tablename__ = 'plugin_visit_stats'
    __table_args__ = (
        sa.Index('idx_plugin_visit_stats_date', 'stats_date', unique=True),
        {'comment': '访问统计表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)

    stats_date: Mapped[date] = mapped_column(sa.Date, comment='统计日期')
    pv: Mapped[int] = mapped_column(sa.Integer, default=0, comment='页面访问量')
    uv: Mapped[int] = mapped_column(sa.Integer, default=0, comment='独立访客数')
