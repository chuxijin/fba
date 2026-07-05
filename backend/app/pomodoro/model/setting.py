#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class PomodoroUserSetting(Base):
    """番茄用户设置表"""

    __tablename__ = 'pomodoro_user_setting'
    __table_args__ = ({'comment': '番茄用户设置表'},)

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, unique=True, index=True, comment='用户 ID')
    focus_minutes: Mapped[int] = mapped_column(default=25, comment='默认专注分钟数')
    short_break_minutes: Mapped[int] = mapped_column(default=5, comment='短休息分钟数')
    long_break_minutes: Mapped[int] = mapped_column(default=15, comment='长休息分钟数')
    long_break_interval: Mapped[int] = mapped_column(default=4, comment='长休息间隔番茄数')
    daily_focus_minutes: Mapped[int] = mapped_column(default=120, comment='每日专注目标分钟数')
    weekly_focus_minutes: Mapped[int] = mapped_column(default=600, comment='每周专注目标分钟数')
    auto_start_break: Mapped[bool] = mapped_column(default=False, comment='是否自动开始休息')
    auto_start_next_focus: Mapped[bool] = mapped_column(default=False, comment='是否自动开始下一轮专注')
    sound_enabled: Mapped[bool] = mapped_column(default=False, comment='是否开启背景音')
    background_sound: Mapped[str | None] = mapped_column(sa.String(50), default=None, comment='背景音')
