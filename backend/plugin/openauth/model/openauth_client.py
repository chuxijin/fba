#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""开放平台授权中心数据模型

openauth_client：第三方应用（skill、插件、外部工具）注册表；
openauth_user_authorization：用户对第三方应用的授权关系。
"""

from datetime import datetime
from uuid import uuid4

import sqlalchemy as sa

from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, id_key
from backend.plugin.openauth.enums import OpenAuthAuthorizationStatus, OpenAuthClientStatus


class OpenAuthClient(Base):
    """第三方应用（客户端）注册表

    每个接入开放平台的应用对应一行记录：skill、插件或外部开发者工具。
    """

    __tablename__ = 'openauth_client'
    __table_args__ = ({'comment': '开放平台客户端注册表'},)

    id: Mapped[id_key] = mapped_column(init=False)
    client_id: Mapped[str] = mapped_column(sa.String(64), unique=True, index=True, comment='客户端标识')
    client_secret_hash: Mapped[str] = mapped_column(sa.String(255), comment='客户端密钥哈希')
    name: Mapped[str] = mapped_column(sa.String(100), comment='应用显示名称（授权页展示）')
    client_type: Mapped[str] = mapped_column(sa.String(20), default='confidential', comment='public/confidential')
    description: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='应用描述')
    icon: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='应用图标 URL')
    scopes: Mapped[list] = mapped_column(JSONB, default_factory=list, comment='允许申请的权限列表')
    redirect_uris: Mapped[list] = mapped_column(JSONB, default_factory=list, comment='允许的回调地址列表')
    status: Mapped[int] = mapped_column(
        default=OpenAuthClientStatus.ENABLED.value,
        index=True,
        comment='状态(0停用 1启用)',
    )


class OpenAuthUserAuthorization(Base):
    """用户与第三方应用的授权关系表

    用户同意授权后写入；重复授权免二次确认的依据；
    用户解绑（revoke）后置为 revoked。
    """

    __tablename__ = 'openauth_user_authorization'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'client_id', name='uk_openauth_user_auth_user_client'),
        sa.Index('idx_openauth_user_auth_user', 'user_id'),
        sa.Index('idx_openauth_user_auth_client', 'client_id'),
        {'comment': '用户与开放平台客户端的授权关系表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, comment='用户 ID')
    client_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey('openauth_client.id', ondelete='CASCADE'), comment='客户端主键 ID'
    )
    grant_version: Mapped[str] = mapped_column(
        sa.String(36), default_factory=lambda: str(uuid4()), comment='授权代次，解绑后旧凭证永不恢复'
    )
    scopes: Mapped[list] = mapped_column(JSONB, default_factory=list, comment='用户实际同意的权限列表')
    status: Mapped[str] = mapped_column(
        sa.String(20),
        default=OpenAuthAuthorizationStatus.ACTIVE.value,
        comment='授权状态(active/revoked)',
    )
    authorized_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近一次授权时间')
    last_used_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近一次使用时间')
