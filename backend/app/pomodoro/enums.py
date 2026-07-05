#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from enum import StrEnum


class PomodoroTaskStatus(StrEnum):
    """番茄任务状态"""

    pending = 'pending'
    doing = 'doing'
    completed = 'completed'
    archived = 'archived'


class PomodoroRepeatType(StrEnum):
    """番茄任务重复类型"""

    none = 'none'
    daily = 'daily'
    weekly = 'weekly'
    monthly = 'monthly'


WEEKDAY_MAP: dict[int, str] = {
    0: '周一',
    1: '周二',
    2: '周三',
    3: '周四',
    4: '周五',
    5: '周六',
    6: '周日',
}


class PomodoroFocusMode(StrEnum):
    """番茄专注模式"""

    pomodoro = 'pomodoro'
    countdown = 'countdown'
    stopwatch = 'stopwatch'


class PomodoroFocusStatus(StrEnum):
    """番茄专注状态"""

    running = 'running'
    paused = 'paused'
    completed = 'completed'
    canceled = 'canceled'


class PomodoroSource(StrEnum):
    """番茄专注来源"""

    mini = 'mini'
    web = 'web'
    admin = 'admin'


class PomodoroHabitStatus(StrEnum):
    """番茄习惯状态"""

    enabled = 'enabled'
    disabled = 'disabled'


class PomodoroBreakType(StrEnum):
    """番茄休息类型"""

    short = 'short'
    long = 'long'


class PomodoroBreakStatus(StrEnum):
    """番茄休息状态"""

    running = 'running'
    completed = 'completed'
    canceled = 'canceled'


class PomodoroAchievementMetric(StrEnum):
    """番茄成就指标"""

    total_focus_hours = 'total_focus_hours'
    focus_streak_days = 'focus_streak_days'
    habit_streak_days = 'habit_streak_days'
    completed_pomodoro_count = 'completed_pomodoro_count'


class PomodoroAchievementStatus(StrEnum):
    """番茄成就状态"""

    achieved = 'achieved'
    claimed = 'claimed'


class PomodoroRankingPeriod(StrEnum):
    """番茄排行榜周期"""

    today = 'today'
    weekly = 'weekly'


class PomodoroRankingScope(StrEnum):
    """番茄排行榜范围"""

    global_ = 'global'


class PomodoroSoundCategory(StrEnum):
    """番茄背景音分类"""

    nature = 'nature'
    ambient = 'ambient'
    noise = 'noise'
