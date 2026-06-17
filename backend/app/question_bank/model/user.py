#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, TimeZone, UniversalText, id_key

if TYPE_CHECKING:
    from backend.app.admin.model import User

    from .practice import PracticeSession, SessionQuestion, WrongQuestionBook
    from .statistics import UserCheckIn


class UserAccount(Base):
    """C端用户账户扩展表（关联 sys_user）"""

    __tablename__ = 'study_user_account'

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='CASCADE'),
        unique=True,
        index=True,
        comment='关联系统用户 ID',
    )
    # 用户画像（精简）
    gender: Mapped[int | None] = mapped_column(default=None, comment='性别（0 未知 1 男 2 女）')
    province: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='省')
    # 渠道信息（精简）
    register_channel: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='注册渠道')
    # 偏好与设置
    study_preference_settings: Mapped[str | None] = mapped_column(
        UniversalText, default=None, comment='刷题偏好设置 JSON'
    )
    privacy_settings: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='隐私设置 JSON')
    theme: Mapped[str] = mapped_column(sa.String(32), default='light', comment='主题')
    last_active_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近活跃时间')

    # 关联系统用户
    user: Mapped['User'] = relationship(init=False, lazy='joined')

    # 代理属性（系统认证模块需要直接访问）
    @property
    def status(self) -> int:
        """用户状态（代理 sys_user.status）"""
        return self.user.status if self.user else 0

    @property
    def username(self) -> str | None:
        """用户名（代理 sys_user.username）"""
        return self.user.username if self.user else None

    @property
    def nickname(self) -> str | None:
        """昵称（代理 sys_user.nickname）"""
        return self.user.nickname if self.user else None

    # ============ 练习刷题关系 ============
    practice_sessions: Mapped[list['PracticeSession']] = relationship(
        init=False, back_populates='account', lazy='noload'
    )
    session_questions: Mapped[list['SessionQuestion']] = relationship(
        init=False, back_populates='account', lazy='noload'
    )
    wrong_questions: Mapped[list['WrongQuestionBook']] = relationship(
        init=False, back_populates='account', lazy='noload'
    )
    check_ins: Mapped[list['UserCheckIn']] = relationship(init=False, back_populates='account', lazy='noload')
