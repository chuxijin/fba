#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.app.pomodoro.enums import PomodoroFocusMode, PomodoroFocusStatus, PomodoroSource
from backend.common.model import Base, TimeZone, UniversalText, id_key


class PomodoroFocusSession(Base):
    """番茄专注记录表"""

    __tablename__ = 'pomodoro_focus_session'
    __table_args__ = (
        sa.Index('idx_pomodoro_focus_user_status', 'user_id', 'status'),
        sa.Index('idx_pomodoro_focus_user_started_at', 'user_id', 'started_at'),
        sa.Index('idx_pomodoro_focus_user_task', 'user_id', 'task_id'),
        {'comment': '番茄专注记录表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='用户 ID')
    started_at: Mapped[datetime] = mapped_column(TimeZone, comment='服务端开始时间')
    mode: Mapped[str] = mapped_column(
        sa.String(20),
        default=PomodoroFocusMode.pomodoro.value,
        comment='专注模式',
    )
    status: Mapped[str] = mapped_column(
        sa.String(20),
        default=PomodoroFocusStatus.running.value,
        comment='专注状态',
    )
    planned_minutes: Mapped[int] = mapped_column(default=25, comment='计划专注分钟数')
    focused_seconds: Mapped[int] = mapped_column(default=0, comment='实际专注秒数')
    paused_seconds: Mapped[int] = mapped_column(default=0, comment='暂停秒数')
    interrupt_count: Mapped[int] = mapped_column(default=0, comment='中断次数')
    source: Mapped[str] = mapped_column(sa.String(20), default=PomodoroSource.mini.value, comment='来源')
    task_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, index=True, comment='关联任务 ID')
    paused_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='最近暂停时间')
    ended_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='结束时间')
    client_started_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='客户端开始时间')
    remark: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='备注')
