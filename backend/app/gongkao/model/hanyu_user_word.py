#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, id_key


class GkHanyuUserWord(Base):
    """用户词语 FSRS 状态表"""

    __tablename__ = 'gk_hanyu_user_word'
    __table_args__ = (
        sa.UniqueConstraint('user_id', 'hanyu_id', name='uq_hanyu_user_word'),
        sa.Index('ix_hanyu_user_word_due', 'user_id', 'state', 'due'),
        {'comment': '用户词语 FSRS 状态表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='用户 ID')
    hanyu_id: Mapped[int] = mapped_column(sa.BigInteger, comment='汉语词汇 ID')
    due: Mapped[datetime] = mapped_column(TimeZone, comment='下次到期时间')
    # FSRS v6 核心字段
    state: Mapped[int] = mapped_column(
        sa.SmallInteger, default=1, comment='FSRS 状态(1 learning 2 review 3 relearning)'
    )
    step: Mapped[int | None] = mapped_column(sa.SmallInteger, default=0, comment='FSRS 学习步骤')
    stability: Mapped[float | None] = mapped_column(sa.Float, default=None, comment='FSRS 稳定性(天)')
    difficulty: Mapped[float | None] = mapped_column(sa.Float, default=None, comment='FSRS 难度')
    last_review: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='上次复习时间')
    # 业务扩展字段
    is_starred: Mapped[bool] = mapped_column(default=False, comment='是否收藏')