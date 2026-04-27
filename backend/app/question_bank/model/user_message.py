#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, UniversalText, id_key

CompatibleJSONB = sa.JSON().with_variant(JSONB, 'postgresql')


class UserMessage(Base):
    """用户消息表"""

    __tablename__ = 'study_user_message'
    __table_args__ = (
        sa.Index('idx_user_message_target_status_time', 'target_type', 'user_id', 'status', 'publish_time'),
        sa.Index('idx_user_message_type_time', 'message_type', 'publish_time'),
        {'comment': '用户消息表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    title: Mapped[str] = mapped_column(sa.String(128), comment='标题')
    content: Mapped[str] = mapped_column(UniversalText, comment='内容')
    target_type: Mapped[str] = mapped_column(
        sa.String(20),
        default='all',
        comment='目标类型: all/user',
    )
    user_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, index=True, comment='用户 ID')
    message_type: Mapped[str] = mapped_column(
        sa.String(32),
        default='system',
        comment='消息类型: system/update/maintenance/personal',
    )
    link_url: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='跳转链接')
    payload: Mapped[dict | None] = mapped_column(CompatibleJSONB, default=None, comment='扩展数据')
    status: Mapped[int] = mapped_column(sa.SmallInteger, default=1, index=True, comment='状态: 0=禁用, 1=启用')
    publish_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='发布时间')
    expire_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='过期时间')
    read_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='个人消息读取时间')


class UserMessageRead(Base):
    """用户消息已读表"""

    __tablename__ = 'study_user_message_read'
    __table_args__ = (
        sa.UniqueConstraint('message_id', 'user_id', name='uq_user_message_read_message_user'),
        sa.Index('idx_user_message_read_user_time', 'user_id', 'read_time'),
        {'comment': '用户消息已读表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    message_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_user_message.id', ondelete='CASCADE'),
        comment='消息 ID',
    )
    user_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='用户 ID')
    read_time: Mapped[datetime] = mapped_column(TimeZone, default_factory=datetime.now, comment='读取时间')
