#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, UserMixin, id_key


class Diary(Base, UserMixin):
    """日记表"""

    __tablename__ = 'jia_diary'

    id: Mapped[id_key] = mapped_column(init=False)
    date: Mapped[int] = mapped_column(BigInteger, index=True, comment='日记日期时间戳')
    content: Mapped[str] = mapped_column(Text, comment='内容(Delta JSON 格式)')
    server_id: Mapped[str | None] = mapped_column(String(100), default=None, index=True, comment='服务器ID')
    category_ids: Mapped[str | None] = mapped_column(Text, default=None, comment='分类ID列表(JSON 数组)')
    tag_ids: Mapped[str | None] = mapped_column(Text, default=None, comment='标签ID列表(JSON 数组)')
    title: Mapped[str | None] = mapped_column(String(500), default=None, comment='标题')
    summary: Mapped[str | None] = mapped_column(Text, default=None, comment='日记摘要/总结')
    mood: Mapped[str | None] = mapped_column(String(50), default=None, comment='主要心情')
    mood_tags: Mapped[str | None] = mapped_column(Text, default=None, comment='多个心情标签(JSON 数组)')
    mood_intensity: Mapped[int | None] = mapped_column(Integer, default=None, comment='心情强度(1-5)')
    weather: Mapped[str | None] = mapped_column(String(50), default=None, comment='天气')
    location: Mapped[str | None] = mapped_column(String(255), default=None, comment='位置')
    attachments: Mapped[str | None] = mapped_column(Text, default=None, comment='附件元数据(JSON 格式)')
    word_count: Mapped[int] = mapped_column(Integer, default=0, comment='字数统计')
    image_count: Mapped[int] = mapped_column(Integer, default=0, comment='图片数量统计')
    video_count: Mapped[int] = mapped_column(Integer, default=0, comment='视频数量统计')
    audio_count: Mapped[int] = mapped_column(Integer, default=0, comment='音频数量统计')
    is_starred: Mapped[int] = mapped_column(Integer, default=0, comment='是否星标/重要(0/1)')
    is_pinned: Mapped[int] = mapped_column(Integer, default=0, comment='是否置顶(0/1)')
    is_encrypted: Mapped[int] = mapped_column(Integer, default=0, comment='是否加密(0/1)')
    priority: Mapped[int] = mapped_column(Integer, default=0, comment='优先级(0-普通/1-重要/2-非常重要)')
    sync_status: Mapped[str] = mapped_column(
        String(20),
        default='synced',
        index=True,
        comment='同步状态: synced/pending/conflict/failed',
    )
    version: Mapped[int] = mapped_column(Integer, default=1, comment='版本号')
    last_synced_at: Mapped[int | None] = mapped_column(BigInteger, default=None, comment='最后同步时间戳')
    deleted_at: Mapped[int | None] = mapped_column(BigInteger, default=None, index=True, comment='软删除时间戳')

