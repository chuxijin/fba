#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date, datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class GetCheckinDetail(SchemaBase):
    """打卡详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='记录 ID')
    user_id: int = Field(description='用户 ID')
    checkin_date: date = Field(description='打卡日期')
    new_words: int = Field(description='当日新学单词数')
    review_words: int = Field(description='当日复习单词数')
    duration_seconds: int = Field(description='学习总时长(秒)')
    streak_days: int = Field(description='连续打卡天数')
    created_time: datetime = Field(description='创建时间')


class GetCheckinToday(SchemaBase):
    """今日打卡状态"""

    is_checked_in: bool = Field(description='是否已打卡')
    new_words: int = Field(default=0, description='今日新学')
    review_words: int = Field(default=0, description='今日复习')
    duration_seconds: int = Field(default=0, description='今日时长(秒)')
    streak_days: int = Field(default=0, description='连续天数')
    daily_target: int = Field(default=20, description='每日目标')
    progress_percent: float = Field(default=0.0, description='完成百分比')


class GetStreakInfo(SchemaBase):
    """连续打卡信息"""

    current_streak: int = Field(description='当前连续打卡天数')
    total_checkins: int = Field(description='总打卡天数')


class CreateCheckinParam(SchemaBase):
    """创建打卡记录参数"""

    user_id: int = Field(description='用户 ID')
    checkin_date: date = Field(description='打卡日期')
    new_words: int = Field(default=0, description='当日新学单词数')
    review_words: int = Field(default=0, description='当日复习单词数')
    duration_seconds: int = Field(default=0, description='学习总时长(秒)')
    streak_days: int = Field(default=0, description='连续打卡天数')
