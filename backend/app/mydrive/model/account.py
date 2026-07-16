#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, TimeZone, id_key

CompatibleJSONB = sa.JSON().with_variant(JSONB, 'postgresql')


class MyDriveAccount(Base):
    """网盘账户表"""

    __tablename__ = 'mydrive_account'
    __table_args__ = (
        sa.UniqueConstraint('owner_id', 'provider', 'external_account_id', name='uq_mydrive_account_owner_provider'),
        sa.Index('idx_mydrive_account_owner_provider_status', 'owner_id', 'provider', 'status'),
        {'comment': '网盘账户表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    owner_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='所属用户 ID')
    provider: Mapped[str] = mapped_column(sa.String(64), comment='网盘驱动标识')
    external_account_id: Mapped[str] = mapped_column(sa.String(256), comment='网盘侧账户标识')
    display_name: Mapped[str] = mapped_column(sa.String(128), comment='账户显示名称')
    credential: Mapped[dict] = mapped_column(CompatibleJSONB, default_factory=dict, comment='授权凭证')
    credential_expires_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='凭证过期时间')
    username: Mapped[str | None] = mapped_column(sa.String(128), default=None, comment='网盘用户名')
    avatar_url: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='头像地址')
    quota: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='总容量（字节）')
    used: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='已用容量（字节）')
    vip_level: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='会员等级')
    status: Mapped[str] = mapped_column(sa.String(32), default='active', comment='状态')
    last_verified_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近验证时间')
    last_profile_synced_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近账户资料同步时间')

    spaces: Mapped[list[MyDriveSpace]] = relationship(
        init=False,
        back_populates='account',
        lazy='noload',
        cascade='all, delete-orphan',
    )
