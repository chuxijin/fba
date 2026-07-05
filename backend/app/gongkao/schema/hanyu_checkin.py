#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date

from pydantic import Field

from backend.common.schema import SchemaBase


class HanyuCheckinInfo(SchemaBase):
    """打卡信息"""

    checkin_date: date = Field(description='日期')
    new_words: int = Field(0, description='新学词语数')
    review_words: int = Field(0, description='复习词语数')
    duration_seconds: int = Field(0, description='学习时长(秒)')
    streak_days: int = Field(0, description='连续打卡天数')


class HanyuCheckinToday(SchemaBase):
    """今日打卡状态"""

    is_checked_in: bool = Field(False, description='今日是否已打卡')
    new_words: int = Field(0, description='今日新学词语数')
    review_words: int = Field(0, description='今日复习词语数')
    duration_seconds: int = Field(0, description='今日学习时长(秒)')
    streak_days: int = Field(0, description='连续打卡天数')
    daily_target: int = Field(20, description='每日新词目标')
    progress_percent: float = Field(0.0, description='今日进度百分比')


class HanyuStreakInfo(SchemaBase):
    """连续打卡信息"""

    current_streak: int = Field(0, description='当前连续打卡天数')
    total_checkins: int = Field(0, description='总打卡天数')


class HanyuCheckinHistoryItem(SchemaBase):
    """打卡历史项"""

    checkin_date: date = Field(description='日期')
    new_words: int = Field(0, description='新学词语数')
    review_words: int = Field(0, description='复习词语数')
    duration_seconds: int = Field(0, description='学习时长(秒)')
    streak_days: int = Field(0, description='连续打卡天数')
