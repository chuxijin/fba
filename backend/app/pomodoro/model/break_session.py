#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.app.pomodoro.enums import PomodoroBreakStatus, PomodoroBreakType, PomodoroSource
from backend.common.model import Base, TimeZone, id_key


class PomodoroBreakSession(Base):
    """番茄休息记录表"""

    __tablename__ = 'pomodoro_break_session'
    __table_args__ = (
        sa.Index('idx_pomodoro_break_user_status', 'user_id', 'status'),
        sa.Index('idx_pomodoro_break_user_started_at', 'user_id', 'started_at'),
        {'comment': '番茄休息记录表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='用户 ID')
    started_at: Mapped[datetime] = mapped_column(TimeZone, comment='服务端开始时间')
    break_type: Mapped[str] = mapped_column(
        sa.String(20),
        default=PomodoroBreakType.short.value,
        comment='休息类型',
    )
    status: Mapped[str] = mapped_column(
        sa.String(20),
        default=PomodoroBreakStatus.running.value,
        comment='休息状态',
    )
    planned_minutes: Mapped[int] = mapped_column(default=5, comment='计划休息分钟数')
    break_seconds: Mapped[int] = mapped_column(default=0, comment='实际休息秒数')
    source: Mapped[str] = mapped_column(sa.String(20), default=PomodoroSource.mini.value, comment='来源')
    focus_session_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, index=True, comment='关联专注记录 ID')
    ended_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='结束时间')
