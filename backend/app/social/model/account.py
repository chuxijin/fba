#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from enum import Enum as PyEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Enum, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, UserMixin, id_key

if TYPE_CHECKING:
    from backend.app.social.model.work import SocialWork


class PlatformEnum(PyEnum):
    """平台枚举"""

    DOUYIN = 'douyin'
    XHS = 'xhs'
    WEIBO = 'weibo'
    QQ = 'qq'
    TIEBA = 'tieba'
    BILIBILI = 'bilibili'
    KUAISHOU = 'kuaishou'


class DomainEnum(PyEnum):
    """领域枚举"""

    CETY = 'cet'  # 四六级
    KAOYAN = 'kaoyan'  # 考研
    GONGKAO = 'gongkao'  # 公考
    JIAOZI = 'jiaozhi'  # 教资
    YINGSHI = 'yingshi'  # 影视
    ZHAOPIN = 'zhaopin'  # 招聘
    WANOU = 'wanou'  # 玩偶


class SocialAccount(Base, UserMixin):
    """账号表"""

    __tablename__ = 'social_account'

    id: Mapped[id_key] = mapped_column(init=False)

    name: Mapped[str] = mapped_column(String(100), index=True, comment='账号名称')
    platform: Mapped[PlatformEnum] = mapped_column(Enum(PlatformEnum), index=True, comment='所属平台')
    domain: Mapped[DomainEnum] = mapped_column(Enum(DomainEnum), index=True, comment='领域')
    homepage: Mapped[str | None] = mapped_column(String(500), default=None, comment='主页地址')
    phone: Mapped[str | None] = mapped_column(String(20), default=None, comment='电话号码')
    account_info: Mapped[dict[str, Any] | None] = mapped_column(JSON, default=None, comment='账号信息(JSON)')

    works: Mapped[list[SocialWork]] = relationship(
        init=False, back_populates='account', cascade='all, delete-orphan', lazy='noload'
    )

    __table_args__ = (
        UniqueConstraint('platform', 'name', name='uk_social_account_platform_name'),
        Index('idx_social_account_platform_homepage', 'platform', 'homepage'),
    )
