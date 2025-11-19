#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import BigInteger, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UserMixin, id_key


class Reminder(Base, UserMixin):
    """提醒表"""

    __tablename__ = 'jia_reminder'

    id: Mapped[id_key] = mapped_column(init=False)
    title: Mapped[str] = mapped_column(String(500), comment='标题')
    scheduled_time: Mapped[int] = mapped_column(BigInteger, index=True, comment='计划时间时间戳')
    server_id: Mapped[str | None] = mapped_column(String(100), default=None, index=True, comment='服务器ID')
    category_ids: Mapped[str | None] = mapped_column(Text, default=None, comment='分类ID列表(JSON 数组)')
    tag_ids: Mapped[str | None] = mapped_column(Text, default=None, comment='标签ID列表(JSON 数组)')
    description: Mapped[str | None] = mapped_column(Text, default=None, comment='描述')
    content: Mapped[str | None] = mapped_column(Text, default=None, comment='内容(Delta JSON 格式)')
    repeat_type: Mapped[str | None] = mapped_column(String(20), default=None, comment='重复类型')
    repeat_config: Mapped[str | None] = mapped_column(Text, default=None, comment='重复配置(JSON)')
    reminder_method: Mapped[str] = mapped_column(
        String(50),
        default='notification',
        comment='提醒方式: notification/email/sms',
    )
    reminder_before_minutes: Mapped[str | None] = mapped_column(Text, default=None, comment='提前提醒分钟数(JSON 数组)')
    attachments: Mapped[str | None] = mapped_column(Text, default=None, comment='附件元数据(JSON 格式)')
    image_count: Mapped[int] = mapped_column(Integer, default=0, comment='图片数量统计')
    video_count: Mapped[int] = mapped_column(Integer, default=0, comment='视频数量统计')
    audio_count: Mapped[int] = mapped_column(Integer, default=0, comment='音频数量统计')
    is_completed: Mapped[int] = mapped_column(Integer, default=0, comment='是否完成(0/1)')
    completed_at: Mapped[int | None] = mapped_column(BigInteger, default=None, comment='完成时间戳')
    is_important: Mapped[int] = mapped_column(Integer, default=0, comment='是否重要(0/1)')
    is_starred: Mapped[int] = mapped_column(Integer, default=0, comment='是否星标(0/1)')
    is_pinned: Mapped[int] = mapped_column(Integer, default=0, comment='是否置顶(0/1)')
    priority: Mapped[int] = mapped_column(Integer, default=0, comment='优先级(0-普通/1-重要/2-紧急)')
    location: Mapped[str | None] = mapped_column(String(255), default=None, comment='位置')
    related_note_ids: Mapped[str | None] = mapped_column(Text, default=None, comment='关联笔记ID列表(JSON 数组)')
    related_diary_ids: Mapped[str | None] = mapped_column(Text, default=None, comment='关联日记ID列表(JSON 数组)')
    related_habit_ids: Mapped[str | None] = mapped_column(Text, default=None, comment='关联习惯ID列表(JSON 数组)')
    completion_rate: Mapped[float] = mapped_column(Float, default=0.0, comment='完成率(0.0-1.0)')
    total_occurrences: Mapped[int] = mapped_column(Integer, default=0, comment='总发生次数')
    completed_occurrences: Mapped[int] = mapped_column(Integer, default=0, comment='已完成次数')
    last_triggered_at: Mapped[int | None] = mapped_column(BigInteger, default=None, comment='最后触发时间戳')
    next_trigger_time: Mapped[int | None] = mapped_column(BigInteger, default=None, index=True, comment='下次触发时间')
    sync_status: Mapped[str] = mapped_column(
        String(20),
        default='synced',
        index=True,
        comment='同步状态: synced/pending/conflict/failed',
    )
    version: Mapped[int] = mapped_column(Integer, default=1, comment='版本号')
    last_synced_at: Mapped[int | None] = mapped_column(BigInteger, default=None, comment='最后同步时间戳')
    deleted_at: Mapped[int | None] = mapped_column(BigInteger, default=None, index=True, comment='软删除时间戳')

