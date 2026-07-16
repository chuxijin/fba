#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.mydrive.model.account import CompatibleJSONB, MyDriveAccount
from backend.common.model import Base, TimeZone, id_key


class MyDriveSpace(Base):
    """文件空间表"""

    __tablename__ = 'mydrive_space'
    __table_args__ = (
        sa.UniqueConstraint('owner_id', 'provider', 'space_type', 'source_key', name='uq_mydrive_space_source'),
        sa.Index('idx_mydrive_space_owner_type_enabled', 'owner_id', 'space_type', 'is_enabled'),
        sa.CheckConstraint(
            "space_type IN ('personal','share_link','group','friend','openlist')",
            name='ck_mydrive_space_type',
        ),
        {'comment': '文件空间表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    owner_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='所属用户 ID')
    provider: Mapped[str] = mapped_column(sa.String(64), comment='网盘驱动标识')
    space_type: Mapped[str] = mapped_column(sa.String(32), comment='文件空间类型')
    name: Mapped[str] = mapped_column(sa.String(128), comment='文件空间名称')
    source_key: Mapped[str] = mapped_column(sa.String(512), comment='来源唯一标识')
    account_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('mydrive_account.id', ondelete='CASCADE'),
        default=None,
        comment='网盘账户 ID',
    )
    root_id: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='根目录 ID')
    root_path: Mapped[str] = mapped_column(sa.String(1024), default='/', comment='根目录路径')
    source_ref: Mapped[dict] = mapped_column(CompatibleJSONB, default_factory=dict, comment='来源定位信息')
    capabilities: Mapped[list[str]] = mapped_column(CompatibleJSONB, default_factory=list, comment='文件空间能力')
    is_enabled: Mapped[bool] = mapped_column(default=True, comment='是否启用')
    last_scanned_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近扫描时间')

    account: Mapped[MyDriveAccount | None] = relationship(init=False, back_populates='spaces', lazy='noload')
