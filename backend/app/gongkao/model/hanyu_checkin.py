#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class GkHanyuCheckin(Base):
    """汉语学习打卡记录表"""

    __tablename__ = 'gk_hanyu_checkin'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'checkin_date', name='uq_hanyu_checkin_user_date'),
        {'comment': '汉语学习打卡记录表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='用户 ID')
    checkin_date: Mapped[date] = mapped_column(sa.Date, comment='打卡日期')
    new_words: Mapped[int] = mapped_column(default=0, comment='当日新学词语数')
    review_words: Mapped[int] = mapped_column(default=0, comment='当日复习词语数')
    duration_seconds: Mapped[int] = mapped_column(default=0, comment='学习总时长(秒)')
    streak_days: Mapped[int] = mapped_column(default=0, comment='连续打卡天数')