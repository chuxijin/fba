#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date

from pydantic import Field

from backend.common.schema import SchemaBase


class GetPomodoroTodayStatistic(SchemaBase):
    """番茄今日统计"""

    statistic_date: date = Field(description='统计日期')
    focused_seconds: int = Field(description='专注秒数')
    completed_task_count: int = Field(description='完成任务数')
    finished_session_count: int = Field(description='完成专注次数')
    habit_checkin_count: int = Field(description='习惯打卡次数')
    daily_focus_goal_minutes: int = Field(description='每日专注目标分钟数')
    daily_focus_progress_percent: float = Field(description='每日专注目标进度')
    current_streak_days: int = Field(description='连续专注天数')


class PomodoroDailyStatisticItem(SchemaBase):
    """番茄每日统计项"""

    statistic_date: date = Field(description='统计日期')
    focused_seconds: int = Field(description='专注秒数')
    completed_task_count: int = Field(description='完成任务数')
    finished_session_count: int = Field(description='完成专注次数')
    habit_checkin_count: int = Field(description='习惯打卡次数')


class GetPomodoroRangeStatistic(SchemaBase):
    """番茄周期统计"""

    start_date: date = Field(description='开始日期')
    end_date: date = Field(description='结束日期')
    focused_seconds: int = Field(description='专注秒数')
    completed_task_count: int = Field(description='完成任务数')
    finished_session_count: int = Field(description='完成专注次数')
    habit_checkin_count: int = Field(description='习惯打卡次数')
    focus_goal_minutes: int = Field(description='专注目标分钟数')
    focus_progress_percent: float = Field(description='专注目标进度')
    days: list[PomodoroDailyStatisticItem] = Field(description='每日统计')


class GetPomodoroCalendarStatistic(GetPomodoroRangeStatistic):
    """番茄日历统计"""

    year: int = Field(description='年份')
    month: int = Field(description='月份')


class PomodoroDistributionItem(SchemaBase):
    """专注分布项"""

    name: str = Field(description='名称')
    color: str | None = Field(None, description='颜色')
    focused_seconds: int = Field(description='专注秒数')
    percentage: float = Field(description='占比百分比')


class PomodoroStatisticPoint(SchemaBase):
    """番茄统计点"""

    period: str = Field(description='周期标识')
    start_date: date = Field(description='开始日期')
    end_date: date = Field(description='结束日期')
    focused_seconds: int = Field(description='专注秒数')
    completed_task_count: int = Field(description='完成任务数')
    finished_session_count: int = Field(description='完成专注次数')


class GetPomodoroSummaryStatistic(SchemaBase):
    """番茄汇总统计"""

    start_date: date = Field(description='开始日期')
    end_date: date = Field(description='结束日期')
    focused_seconds: int = Field(description='专注秒数')
    completed_task_count: int = Field(description='完成任务数')
    finished_session_count: int = Field(description='完成专注次数')
    avg_task_seconds: int = Field(description='任务平均秒数')
    points: list[PomodoroStatisticPoint] = Field(description='统计点')
    distribution: list[PomodoroDistributionItem] = Field(description='分布数据')
