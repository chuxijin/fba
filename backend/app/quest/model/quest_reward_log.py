#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, id_key


class QuestRewardLog(Base):
    """悬赏任务奖励发放流水表"""

    __tablename__ = 'quest_reward_log'
    __table_args__ = (
        sa.Index('idx_quest_reward_log_quest_user', 'quest_id', 'user_id'),
        {'comment': '悬赏任务奖励发放流水表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    claim_id: Mapped[int] = mapped_column(sa.BigInteger, unique=True, comment='关联领取记录 ID')
    quest_id: Mapped[int] = mapped_column(sa.BigInteger, comment='任务 ID')
    user_id: Mapped[int] = mapped_column(sa.BigInteger, comment='用户 ID')
    reward_type: Mapped[str] = mapped_column(sa.String(32), comment='奖励类型快照')
    source_key: Mapped[str] = mapped_column(sa.String(128), unique=True, comment='幂等键')
    reward_data: Mapped[dict | None] = mapped_column(sa.JSON, default=None, comment='奖励数据快照')
    grant_status: Mapped[int] = mapped_column(
        sa.SmallInteger,
        default=0,
        comment='发放状态(0 待发放 1 成功 2 失败 3 已撤销)',
    )
    error_message: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='失败原因')
    granted_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='发放完成时间')
