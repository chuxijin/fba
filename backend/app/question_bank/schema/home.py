#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""首页相关 Schema"""
import datetime
from decimal import Decimal

from pydantic import Field

from backend.common.schema import SchemaBase


class DailyPractice(SchemaBase):
    """每日练习明细"""

    date: datetime.date = Field(description='日期')
    count: int = Field(description='做题数量')
    correct_count: int = Field(description='答对数量')
    duration: int = Field(description='练习时长（秒）')


class WeekPracticeStats(SchemaBase):
    """本周刷题统计"""

    total_count: int = Field(description='本周做题总数')
    correct_count: int = Field(description='本周答对数量')
    accuracy_rate: Decimal = Field(description='本周正确率（0-100）')
    total_duration: int = Field(description='本周总时长（秒）')
    daily_breakdown: list[DailyPractice] = Field(description='每日明细')


class CheckInInfo(SchemaBase):
    """打卡信息"""

    check_in_streak: int = Field(description='连续打卡天数')
    total_check_in_days: int = Field(description='累计打卡天数')
    is_checked_in_today: bool = Field(description='今日是否已打卡')
    today_practice_count: int = Field(description='今日做题数')


class UserRankInfo(SchemaBase):
    """用户排名信息"""

    beat_percentage: Decimal = Field(description='击败用户百分比（0-100）')
    current_rank: int = Field(description='当前排名')
    total_users: int = Field(description='总用户数')
    yesterday_rank: int | None = Field(None, description='昨日排名')
    rank_change: int | None = Field(None, description='排名变化（正数上升，负数下降）')


class HomeUserReportData(SchemaBase):
    """用户报告统计"""

    total_answer_count: int = Field(description='总答题量')
    accuracy_rate: Decimal = Field(description='正确率（0-100）')
    site_max_answer_count: int = Field(description='全站最高答题量')
    answer_count_rank: int = Field(description='答题量排名')
    practice_days: int = Field(description='练习天数')
    total_answer_duration: int = Field(description='答题时长（秒）')
    created_session_count: int = Field(description='创建练习数')


class HomeDashboardData(SchemaBase):
    """首页 Dashboard 数据"""

    check_in: CheckInInfo = Field(description='打卡信息')
    week_stats: WeekPracticeStats = Field(description='本周刷题统计')
    rank: UserRankInfo = Field(description='排名信息')
    total_questions: int = Field(description='累计做题数')
    total_correct: int = Field(description='累计答对数')
    overall_accuracy: Decimal = Field(description='总体正确率（0-100）')
    report: HomeUserReportData = Field(description='用户报告统计')


class CheckInParam(SchemaBase):
    """打卡参数"""

    practice_count: int = Field(description='当日做题数')
    practice_duration: int = Field(description='当日练习时长（秒）')


class CheckInResult(SchemaBase):
    """打卡结果"""

    is_checked_in_today: bool = Field(description='今日是否已打卡')
    is_already_checked_in: bool = Field(description='是否重复打卡')
    check_in_streak: int = Field(description='连续打卡天数')
    total_check_in_days: int = Field(description='累计打卡天数')
    practice_count: int = Field(description='当日做题数')
    practice_duration: int = Field(description='当日练习时长（秒）')
    reward_exp: int = Field(description='本次奖励经验')
    family_code: str | None = Field(default=None, description='入账等级族群')
    tier_grade: int | None = Field(default=None, description='当前等级')
    exp: int | None = Field(default=None, description='累计经验')
    available_exp: int | None = Field(default=None, description='可用经验')


class CheckInCalendarDay(SchemaBase):
    """打卡日历单日数据"""

    date: datetime.date = Field(description='日期')
    is_checked_in: bool = Field(description='是否已打卡')
    practice_count: int = Field(default=0, description='做题数量')


class CheckInCalendarData(SchemaBase):
    """打卡日历数据"""

    year: int = Field(description='年份')
    month: int = Field(description='月份')
    days: list[CheckInCalendarDay] = Field(description='每日打卡数据')
    total_check_in_days: int = Field(description='本月打卡天数')


class RankUserInfo(SchemaBase):
    """排行榜用户信息"""

    user_id: int = Field(description='用户 ID')
    nickname: str = Field(description='昵称')
    avatar: str | None = Field(None, description='头像 URL')


class RankItem(SchemaBase):
    """排行榜条目"""

    rank: int = Field(description='排名')
    user: RankUserInfo = Field(description='用户信息')
    value: int | Decimal = Field(description='统计值（刷题数/正确率/坚持天数）')
    is_current_user: bool = Field(default=False, description='是否为当前用户')


class RankListData(SchemaBase):
    """排行榜列表数据"""

    rank_type: str = Field(description='排行榜类型（practice_count/accuracy_rate/streak_days）')
    current_user_rank: RankItem | None = Field(None, description='当前用户排名（可能不在前 100）')
    top_users: list[RankItem] = Field(description='排行榜用户列表')
