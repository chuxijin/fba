#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UniversalText, id_key


class UserSocialAccount(Base):
    """用户社交账号绑定表"""

    __tablename__ = 'sys_social_account'
    __table_args__ = (
        sa.UniqueConstraint('platform', 'openid', name='uq_social_platform_openid'),
        sa.Index('ix_social_unionid', 'unionid'),
        {'comment': '社交账号绑定表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='关联系统用户 ID')
    platform: Mapped[str] = mapped_column(sa.String(32), comment='平台标识')
    openid: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='平台 OpenID')
    unionid: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='微信 UnionID')
    sid: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='第三方用户 ID')
    session_key: Mapped[str | None] = mapped_column(sa.String(256), default=None, comment='小程序 SessionKey')
    access_token: Mapped[str | None] = mapped_column(sa.String(512), default=None, comment='OAuth2 AccessToken')
    extra: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='平台特有数据 JSON')
    status: Mapped[int] = mapped_column(default=1, comment='状态(0解绑 1正常)')
