#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from sqlalchemy import BigInteger, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UserMixin, id_key


class Habit(Base, UserMixin):
    """习惯表"""

    __tablename__ = 'jia_habit'

    id: Mapped[id_key] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(String(255), comment='习惯名称')
    server_id: Mapped[str | None] = mapped_column(String(100), default=None, index=True, comment='服务器ID')
    description: Mapped[str | None] = mapped_column(Text, default=None, comment='习惯简短描述')
    content: Mapped[str | None] = mapped_column(Text, default=None, comment='习惯详细内容(Delta JSON 格式)')
    icon: Mapped[str | None] = mapped_column(String(100), default=None, comment='图标')
    color: Mapped[str | None] = mapped_column(String(50), default=None, comment='颜色标记')
    category_ids: Mapped[str | None] = mapped_column(Text, default=None, comment='分类ID列表(JSON 数组)')
    tag_ids: Mapped[str | None] = mapped_column(Text, default=None, comment='标签ID列表(JSON 数组)')
    difficulty: Mapped[int] = mapped_column(Integer, default=1, comment='难度等级(1-简单/2-中等/3-困难)')
    motivation: Mapped[str | None] = mapped_column(Text, default=None, comment='动力/原因描述')
    reward: Mapped[str | None] = mapped_column(Text, default=None, comment='奖励描述')
    target_type: Mapped[str | None] = mapped_column(String(20), default=None, comment='目标类型: daily/weekly/monthly')
    target_value: Mapped[int | None] = mapped_column(Integer, default=None, comment='目标值')
    start_date: Mapped[int | None] = mapped_column(BigInteger, default=None, comment='习惯开始日期时间戳')
    end_date: Mapped[int | None] = mapped_column(BigInteger, default=None, comment='习惯预计结束日期')
    duration_days: Mapped[int | None] = mapped_column(Integer, default=None, comment='习惯持续天数')
    reminder_enabled: Mapped[int] = mapped_column(Integer, default=1, comment='是否启用提醒(0/1)')
    reminder_time: Mapped[str | None] = mapped_column(String(10), default=None, comment='提醒时间(HH:mm)')
    reminder_days: Mapped[str | None] = mapped_column(Text, default=None, comment='提醒日期(JSON 数组)')
    attachments: Mapped[str | None] = mapped_column(Text, default=None, comment='附件元数据(JSON 格式)')
    image_count: Mapped[int] = mapped_column(Integer, default=0, comment='图片数量统计')
    video_count: Mapped[int] = mapped_column(Integer, default=0, comment='视频数量统计')
    audio_count: Mapped[int] = mapped_column(Integer, default=0, comment='音频数量统计')
    current_streak: Mapped[int] = mapped_column(Integer, default=0, comment='当前连续天数')
    longest_streak: Mapped[int] = mapped_column(Integer, default=0, comment='最长连续天数')
    total_completed: Mapped[int] = mapped_column(Integer, default=0, comment='总完成次数')
    success_rate: Mapped[float] = mapped_column(Float, default=0.0, comment='成功率(0.0-1.0)')
    last_checkin_date: Mapped[int | None] = mapped_column(BigInteger, default=None, comment='最后打卡日期')
    is_archived: Mapped[int] = mapped_column(Integer, default=0, comment='是否归档(0/1)')
    is_pinned: Mapped[int] = mapped_column(Integer, default=0, comment='是否置顶(0/1)')
    sync_status: Mapped[str] = mapped_column(
        String(20),
        default='synced',
        index=True,
        comment='同步状态: synced/pending/conflict/failed',
    )
    version: Mapped[int] = mapped_column(Integer, default=1, comment='版本号')
    last_synced_at: Mapped[int | None] = mapped_column(BigInteger, default=None, comment='最后同步时间戳')
    deleted_at: Mapped[int | None] = mapped_column(BigInteger, default=None, index=True, comment='软删除时间戳')


class HabitRecord(Base, UserMixin):
    """习惯打卡记录表"""

    __tablename__ = 'jia_habit_record'
    __table_args__ = (
        UniqueConstraint('habit_id', 'date', name='uq_habit_date'),
        {'comment': '习惯打卡记录表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    habit_id: Mapped[int] = mapped_column(
        ForeignKey('jia_habit.id', ondelete='CASCADE'),
        index=True,
        comment='习惯ID',
    )
    date: Mapped[int] = mapped_column(BigInteger, index=True, comment='打卡日期时间戳')
    server_id: Mapped[str | None] = mapped_column(String(100), default=None, index=True, comment='服务器ID')
    habit_server_id: Mapped[str | None] = mapped_column(String(100), default=None, comment='习惯服务器ID')
    checkin_time: Mapped[int | None] = mapped_column(BigInteger, default=None, comment='打卡时间戳')
    count: Mapped[int] = mapped_column(Integer, default=1, comment='当天完成次数')
    completion_percentage: Mapped[float | None] = mapped_column(Float, default=None, comment='完成百分比(0.0-1.0)')
    note: Mapped[str | None] = mapped_column(Text, default=None, comment='备注')
    mood: Mapped[str | None] = mapped_column(String(50), default=None, comment='打卡时的心情')
    location: Mapped[str | None] = mapped_column(String(255), default=None, comment='打卡位置')
    attachments: Mapped[str | None] = mapped_column(Text, default=None, comment='附件元数据(JSON 格式)')
    image_count: Mapped[int] = mapped_column(Integer, default=0, comment='图片数量统计')
    checkin_type: Mapped[str] = mapped_column(
        String(20),
        default='manual',
        comment='打卡类型: manual-手动/auto-自动/reminder-提醒触发',
    )
    status: Mapped[str] = mapped_column(
        String(20),
        default='completed',
        comment='状态: completed-完成/partial-部分完成/failed-未完成',
    )
    sync_status: Mapped[str] = mapped_column(
        String(20),
        default='synced',
        index=True,
        comment='同步状态: synced/pending/conflict/failed',
    )
    version: Mapped[int] = mapped_column(Integer, default=1, comment='版本号')
    last_synced_at: Mapped[int | None] = mapped_column(BigInteger, default=None, comment='最后同步时间戳')
    deleted_at: Mapped[int | None] = mapped_column(BigInteger, default=None, index=True, comment='软删除时间戳')

