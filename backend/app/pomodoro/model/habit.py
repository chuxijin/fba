#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date, datetime

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.app.pomodoro.enums import PomodoroHabitStatus
from backend.common.model import Base, TimeZone, id_key


class PomodoroHabit(Base):
    """番茄习惯表"""

    __tablename__ = 'pomodoro_habit'
    __table_args__ = (
        sa.Index('idx_pomodoro_habit_user_status', 'user_id', 'status'),
        {'comment': '番茄习惯表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='用户 ID')
    name: Mapped[str] = mapped_column(sa.String(100), comment='习惯名称')
    target_count: Mapped[int] = mapped_column(default=1, comment='每日目标次数')
    repeat_days: Mapped[str | None] = mapped_column(sa.String(20), default=None, comment='自定义重复星期，逗号分隔，0=周一...6=周日')
    status: Mapped[str] = mapped_column(
        sa.String(20),
        default=PomodoroHabitStatus.enabled.value,
        comment='习惯状态',
    )


class PomodoroHabitCheckin(Base):
    """番茄习惯打卡表"""

    __tablename__ = 'pomodoro_habit_checkin'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'habit_id', 'checkin_date', name='uk_pomodoro_habit_checkin_user_habit_date'),
        sa.Index('idx_pomodoro_habit_checkin_user_date', 'user_id', 'checkin_date'),
        {'comment': '番茄习惯打卡表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='用户 ID')
    habit_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='习惯 ID')
    checkin_date: Mapped[date] = mapped_column(sa.Date, comment='打卡日期')
    checked_at: Mapped[datetime] = mapped_column(TimeZone, comment='最近打卡时间')
    count: Mapped[int] = mapped_column(default=1, comment='当日打卡次数')
