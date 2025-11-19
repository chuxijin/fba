#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import BigInteger, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UserMixin, id_key


class Tag(Base, UserMixin):
    """标签表"""

    __tablename__ = 'jia_tag'
    __table_args__ = (
        UniqueConstraint('created_by', 'name', name='uq_user_tag_name'),
        {'comment': '标签表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(String(100), comment='标签名称')
    server_id: Mapped[str | None] = mapped_column(String(100), default=None, index=True, comment='服务器ID')
    color: Mapped[str | None] = mapped_column(String(50), default=None, comment='标签颜色')
    sync_status: Mapped[str] = mapped_column(
        String(20),
        default='synced',
        index=True,
        comment='同步状态: synced/pending/conflict/failed',
    )
    last_synced_at: Mapped[int | None] = mapped_column(BigInteger, default=None, comment='最后同步时间戳')
    version: Mapped[int] = mapped_column(Integer, default=1, comment='版本号')
    deleted_at: Mapped[int | None] = mapped_column(BigInteger, default=None, index=True, comment='软删除时间戳')

