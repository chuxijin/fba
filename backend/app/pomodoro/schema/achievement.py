#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.app.pomodoro.enums import PomodoroAchievementMetric, PomodoroAchievementStatus
from backend.common.schema import SchemaBase


class CreatePomodoroAchievementRuleInternal(SchemaBase):
    """创建番茄成就规则内部参数"""

    code: str = Field(description='规则编码')
    name: str = Field(description='成就名称')
    description: str | None = Field(None, description='成就描述')
    metric: PomodoroAchievementMetric = Field(description='成就指标')
    threshold_value: int = Field(description='达成阈值')
    badge_level: str = Field('bronze', description='徽章等级')
    icon: str | None = Field(None, description='图标标识')
    sort: int = Field(0, description='排序')
    is_enabled: bool = Field(True, description='是否启用')


class CreatePomodoroUserAchievementInternal(SchemaBase):
    """创建番茄用户成就内部参数"""

    user_id: int = Field(description='用户 ID')
    rule_id: int = Field(description='成就规则 ID')
    status: PomodoroAchievementStatus = Field(PomodoroAchievementStatus.achieved, description='成就状态')
    progress_value: int = Field(0, description='达成时进度值')
    achieved_at: datetime = Field(description='达成时间')
    claimed_at: datetime | None = Field(None, description='领取时间')


class GetPomodoroAchievementRuleDetail(SchemaBase):
    """番茄成就规则详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='成就规则 ID')
    code: str = Field(description='规则编码')
    name: str = Field(description='成就名称')
    description: str | None = Field(None, description='成就描述')
    metric: PomodoroAchievementMetric = Field(description='成就指标')
    threshold_value: int = Field(description='达成阈值')
    badge_level: str = Field(description='徽章等级')
    icon: str | None = Field(None, description='图标标识')
    sort: int = Field(description='排序')
    is_enabled: bool = Field(description='是否启用')


class GetPomodoroUserAchievementDetail(SchemaBase):
    """番茄用户成就详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='用户成就 ID')
    user_id: int = Field(description='用户 ID')
    rule_id: int = Field(description='成就规则 ID')
    status: PomodoroAchievementStatus = Field(description='成就状态')
    progress_value: int = Field(description='达成时进度值')
    achieved_at: datetime = Field(description='达成时间')
    claimed_at: datetime | None = Field(None, description='领取时间')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class PomodoroAchievementItem(SchemaBase):
    """番茄成就项"""

    rule: GetPomodoroAchievementRuleDetail = Field(description='成就规则')
    user_achievement: GetPomodoroUserAchievementDetail | None = Field(None, description='用户成就记录')
    current_value: int = Field(description='当前进度值')
    progress_percent: float = Field(description='进度百分比')
    achieved: bool = Field(description='是否已达成')
    claimed: bool = Field(description='是否已领取')


class GetPomodoroAchievementList(SchemaBase):
    """番茄成就列表"""

    total_focus_hours: int = Field(description='累计专注小时数')
    focus_streak_days: int = Field(description='连续专注天数')
    habit_streak_days: int = Field(description='连续习惯打卡天数')
    completed_pomodoro_count: int = Field(description='完成番茄数量')
    items: list[PomodoroAchievementItem] = Field(description='成就列表')
