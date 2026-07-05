#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date, datetime
from typing import Optional

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.pomodoro.enums import PomodoroRepeatType, PomodoroTaskStatus
from backend.common.model import Base, TimeZone, UniversalText, id_key


class PomodoroTask(Base):
    """番茄任务表"""

    __tablename__ = 'pomodoro_task'
    __table_args__ = (
        sa.Index('idx_pomodoro_task_user_status', 'user_id', 'status'),
        sa.Index('idx_pomodoro_task_user_due_at', 'user_id', 'due_at'),
        sa.Index('idx_pomodoro_task_user_created_time', 'user_id', 'created_time'),
        sa.Index('idx_pomodoro_task_parent_id', 'parent_id'),
        {'comment': '番茄任务表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='用户 ID')
    title: Mapped[str] = mapped_column(sa.String(100), comment='任务标题')
    status: Mapped[str] = mapped_column(
        sa.String(20),
        default=PomodoroTaskStatus.pending.value,
        comment='任务状态',
    )
    priority: Mapped[int] = mapped_column(default=0, comment='优先级')
    repeat_type: Mapped[str] = mapped_column(
        sa.String(20),
        default=PomodoroRepeatType.none.value,
        comment='重复类型',
    )
    description: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='任务描述')
    estimated_minutes: Mapped[int | None] = mapped_column(default=None, comment='预计完成分钟数')
    due_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='截止时间')
    completed_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='完成时间')
    source_task_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, index=True, comment='重复来源任务 ID')
    schedule_date: Mapped[date | None] = mapped_column(sa.Date, default=None, index=True, comment='计划日期')
    repeat_days: Mapped[str | None] = mapped_column(sa.String(20), default=None, comment='自定义重复星期，逗号分隔，0=周一...6=周日')
    repeat_key: Mapped[str | None] = mapped_column(sa.String(64), unique=True, default=None, comment='重复实例唯一键')
    parent_id: Mapped[int | None] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('pomodoro_task.id', ondelete='SET NULL'),
        default=None,
        comment='父任务 ID',
    )

    # 父子任务关系
    parent: Mapped[Optional['PomodoroTask']] = relationship(
        init=False, back_populates='children', remote_side='PomodoroTask.id'
    )
    children: Mapped[list['PomodoroTask']] = relationship(init=False, back_populates='parent')
