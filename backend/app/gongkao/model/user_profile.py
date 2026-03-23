#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, id_key

CompatibleJSONB = sa.JSON().with_variant(JSONB, 'postgresql')

if TYPE_CHECKING:
    from backend.app.admin.model.user import User


class GkUserProfile(Base):
    """公考用户画像表"""

    __tablename__ = 'gk_user_profile'
    __table_args__ = (
        sa.UniqueConstraint('user_id', name='uq_gk_user_profile_user_id'),
        sa.CheckConstraint('total_work_years >= 0', name='ck_gk_user_profile_total_work_years_nonneg'),
        {'comment': '公考用户画像表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('sys_user.id', ondelete='CASCADE'),
        unique=True,
        index=True,
        comment='关联系统用户 ID',
    )

    # 基础画像
    birth_date: Mapped[date | None] = mapped_column(sa.Date, default=None, comment='出生日期')
    gender: Mapped[str | None] = mapped_column(sa.String(10), default=None, comment='性别')
    ethnicity: Mapped[str | None] = mapped_column(sa.String(50), default=None, comment='民族')
    hukou_region_code: Mapped[str | None] = mapped_column(sa.String(20), default=None, comment='户籍地区代码')
    origin_region_code: Mapped[str | None] = mapped_column(sa.String(20), default=None, comment='生源地区代码')
    politics: Mapped[str | None] = mapped_column(sa.String(50), default=None, comment='政治面貌')
    special_identity: Mapped[str | None] = mapped_column(sa.String(200), default=None, comment='特殊身份信息')
    is_fresh_graduate: Mapped[bool] = mapped_column(sa.Boolean, default=False, comment='是否应届生')
    total_work_years: Mapped[int] = mapped_column(sa.Integer, default=0, comment='总工作年限(月)')

    # 扩展画像 JSONB
    educations: Mapped[list[dict[str, Any]] | None] = mapped_column(
        CompatibleJSONB,
        default=None,
        comment='教育经历 JSONB',
    )
    region_preferences: Mapped[list[dict[str, Any]] | None] = mapped_column(
        CompatibleJSONB,
        default=None,
        comment='地区偏好 JSONB',
    )
    certificates: Mapped[list[dict[str, Any]] | None] = mapped_column(
        CompatibleJSONB,
        default=None,
        comment='证书信息 JSONB',
    )
    work_experiences: Mapped[list[dict[str, Any]] | None] = mapped_column(
        CompatibleJSONB,
        default=None,
        comment='工作经历 JSONB',
    )
    honors: Mapped[list[dict[str, Any]] | None] = mapped_column(
        CompatibleJSONB,
        default=None,
        comment='荣誉信息 JSONB',
    )
    profile_extra: Mapped[dict[str, Any] | None] = mapped_column(
        CompatibleJSONB,
        default=None,
        comment='其他画像扩展 JSONB',
    )

    user: Mapped[User] = relationship(init=False, lazy='joined')
