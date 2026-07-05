#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.app.pomodoro.enums import PomodoroAchievementMetric, PomodoroAchievementStatus
from backend.common.model import Base, TimeZone, UniversalText, id_key


class PomodoroAchievementRule(Base):
    """番茄成就规则表"""

    __tablename__ = 'pomodoro_achievement_rule'
    __table_args__ = (
        sa.Index('idx_pomodoro_achievement_rule_metric', 'metric', 'threshold_value'),
        {'comment': '番茄成就规则表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    code: Mapped[str] = mapped_column(sa.String(64), unique=True, index=True, comment='规则编码')
    name: Mapped[str] = mapped_column(sa.String(100), comment='成就名称')
    metric: Mapped[str] = mapped_column(sa.String(50), comment='成就指标')
    threshold_value: Mapped[int] = mapped_column(comment='达成阈值')
    description: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='成就描述')
    badge_level: Mapped[str] = mapped_column(sa.String(20), default='bronze', comment='徽章等级')
    icon: Mapped[str | None] = mapped_column(sa.String(100), default=None, comment='图标标识')
    sort: Mapped[int] = mapped_column(default=0, comment='排序')
    is_enabled: Mapped[bool] = mapped_column(default=True, comment='是否启用')


class PomodoroUserAchievement(Base):
    """番茄用户成就表"""

    __tablename__ = 'pomodoro_user_achievement'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'rule_id', name='uk_pomodoro_user_achievement_user_rule'),
        sa.Index('idx_pomodoro_user_achievement_user_status', 'user_id', 'status'),
        {'comment': '番茄用户成就表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='用户 ID')
    rule_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='成就规则 ID')
    achieved_at: Mapped[datetime] = mapped_column(TimeZone, comment='达成时间')
    status: Mapped[str] = mapped_column(
        sa.String(20),
        default=PomodoroAchievementStatus.achieved.value,
        comment='成就状态',
    )
    progress_value: Mapped[int] = mapped_column(default=0, comment='达成时进度值')
    claimed_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='领取时间')
