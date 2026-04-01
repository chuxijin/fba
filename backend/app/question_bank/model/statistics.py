#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""统计相关模型"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import Base, TimeZone, UserMixin, id_key
from backend.utils.timezone import timezone

if TYPE_CHECKING:
    from .user import UserAccount


class UserCheckIn(Base, UserMixin):
    """用户打卡表"""

    __tablename__ = 'study_user_check_in'
    __table_args__ = (
        sa.Index('idx_checkin_user_date', 'user_id', 'check_date', unique=True),
        sa.Index('idx_checkin_date', 'check_date'),
        {'comment': '用户打卡表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_user_account.user_id', ondelete='CASCADE'),
        comment='用户 ID',
    )
    check_date: Mapped[date] = mapped_column(comment='打卡日期')
    check_time: Mapped[datetime] = mapped_column(
        TimeZone,
        init=False,
        default_factory=timezone.now,
        comment='打卡时间',
    )
    practice_count: Mapped[int] = mapped_column(default=0, comment='当日做题数')
    practice_duration: Mapped[int] = mapped_column(default=0, comment='当日练习时长（秒）')

    account: Mapped['UserAccount'] = relationship(init=False, back_populates='check_ins', lazy='noload')


class UserDailyRank(Base):
    """用户每日排名表（预计算）"""

    __tablename__ = 'study_user_daily_rank'
    __table_args__ = (
        sa.Index('idx_rank_user_date', 'user_id', 'rank_date'),
        sa.Index('idx_rank_date', 'rank_date'),
        sa.UniqueConstraint('user_id', 'rank_date', name='uq_user_rank_date'),
        {'comment': '用户每日排名表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, comment='用户 ID')
    rank_date: Mapped[date] = mapped_column(comment='排名日期')
    rank: Mapped[int] = mapped_column(comment='排名')
    total_users: Mapped[int] = mapped_column(comment='总用户数')
    beat_percentage: Mapped[Decimal] = mapped_column(
        sa.Numeric(5, 2),
        comment='击败用户百分比（0-100）'
    )
    practice_count: Mapped[int] = mapped_column(comment='当日练习数量')
    correct_count: Mapped[int] = mapped_column(default=0, comment='当日答对数量')
    accuracy_rate: Mapped[Decimal] = mapped_column(
        sa.Numeric(5, 2),
        default=Decimal('0'),
        comment='当日正确率（0-100）',
    )
    created_time: Mapped[datetime] = mapped_column(
        TimeZone,
        init=False,
        server_default=sa.func.now(),
        comment='创建时间',
    )


class UserPracticeStats(Base):
    """用户刷题统计快照表"""

    __tablename__ = 'study_user_practice_stats'
    __table_args__ = (
        {'comment': '用户刷题统计快照表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('study_user_account.user_id', ondelete='CASCADE'),
        unique=True,
        comment='用户 ID',
    )
    total_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='累计答题数（已判题）')
    correct_count: Mapped[int] = mapped_column(sa.Integer, default=0, comment='累计答对数')
    total_duration: Mapped[int] = mapped_column(sa.Integer, default=0, comment='累计答题时长（秒）')
    practice_days: Mapped[int] = mapped_column(sa.Integer, default=0, comment='练习天数')
    last_practice_date: Mapped[date | None] = mapped_column(default=None, comment='最后练习日期')

