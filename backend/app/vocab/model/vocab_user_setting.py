#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class VocabUserSetting(Base):
    """用户学习设置表"""

    __tablename__ = 'vocab_user_setting'
    __table_args__ = {'comment': '用户学习设置表'}

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, unique=True, index=True, comment='用户 ID')
    daily_new_target: Mapped[int] = mapped_column(default=20, comment='每日新词目标')
    daily_review_limit: Mapped[int] = mapped_column(default=200, comment='每日复习上限(0 不限)')
    reminder_enabled: Mapped[bool] = mapped_column(default=False, comment='是否开启提醒')
    reminder_time: Mapped[str | None] = mapped_column(sa.String(5), default=None, comment='提醒时间(如 08:30)')
    preferred_mode: Mapped[str] = mapped_column(sa.String(20), default='recognize', comment='偏好学习模式')
    auto_pronunciation: Mapped[bool] = mapped_column(default=True, comment='自动播放发音')
    pronunciation_type: Mapped[str] = mapped_column(sa.String(5), default='us', comment='发音偏好(us/uk)')
