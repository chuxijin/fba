#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, UniversalText, id_key

CompatibleJSONB = sa.JSON().with_variant(JSONB, 'postgresql')


class MessageTargetType:
    """消息投递目标类型"""

    ALL = 'all'
    USER = 'user'
    ROLE = 'role'


class MessageType:
    """消息业务类型"""

    SYSTEM = 'system'
    UPDATE = 'update'
    MAINTENANCE = 'maintenance'
    PERSONAL = 'personal'


class MessageStatus:
    """消息状态"""

    DISABLED = 0
    ENABLED = 1


class Message(Base):
    """系统消息表（站内信收件箱来源）"""

    __tablename__ = 'sys_message'
    __table_args__ = (
        sa.Index('idx_message_target_status_time', 'target_type', 'user_id', 'status', 'publish_time'),
        sa.Index('idx_message_type_time', 'message_type', 'publish_time'),
        sa.Index('idx_message_biz', 'biz_source', 'biz_id'),
        {'comment': '系统消息表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    title: Mapped[str] = mapped_column(sa.String(128), comment='标题')
    content: Mapped[str] = mapped_column(UniversalText, comment='内容')
    target_type: Mapped[str] = mapped_column(
        sa.String(20),
        default=MessageTargetType.ALL,
        comment='目标类型: all/user/role',
    )
    user_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        default=None,
        index=True,
        comment='目标用户 ID（target_type=user 时）',
    )
    role_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        default=None,
        comment='目标角色 ID（target_type=role 时）',
    )
    message_type: Mapped[str] = mapped_column(
        sa.String(32),
        default=MessageType.SYSTEM,
        comment='消息类型: system/update/maintenance/personal',
    )
    biz_source: Mapped[str | None] = mapped_column(
        sa.String(32),
        default=None,
        comment='来源模块，如 question_bank_v2',
    )
    biz_id: Mapped[str | None] = mapped_column(
        sa.String(64),
        default=None,
        comment='来源业务对象 ID，前端可点回原处',
    )
    sender_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        default=None,
        comment='发送人 ID（系统自动发送为空）',
    )
    link_url: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='跳转链接')
    payload: Mapped[dict | None] = mapped_column(CompatibleJSONB, default=None, comment='扩展数据')
    status: Mapped[int] = mapped_column(
        sa.SmallInteger,
        default=MessageStatus.ENABLED,
        index=True,
        comment='状态: 0=禁用, 1=启用',
    )
    publish_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='发布时间')
    expire_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='过期时间')


class MessageRead(Base):
    """系统消息已读表（全站/单人/角色统一走此表）"""

    __tablename__ = 'sys_message_read'
    __table_args__ = (
        sa.UniqueConstraint('message_id', 'user_id', name='uq_message_read_message_user'),
        sa.Index('idx_message_read_user_time', 'user_id', 'read_time'),
        {'comment': '系统消息已读表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    message_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_message.id', ondelete='CASCADE'),
        comment='消息 ID',
    )
    user_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='用户 ID')
    read_time: Mapped[datetime] = mapped_column(TimeZone, default_factory=datetime.now, comment='读取时间')
