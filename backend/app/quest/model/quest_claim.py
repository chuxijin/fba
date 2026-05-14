#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, UniversalText, id_key


class QuestClaim(Base):
    """悬赏任务领取记录表"""

    __tablename__ = 'quest_claim'
    __table_args__ = (
        sa.Index('idx_quest_claim_quest_user', 'quest_id', 'user_id'),
        sa.Index('idx_quest_claim_status', 'claim_status'),
        {'comment': '悬赏任务领取记录表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    quest_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='任务 ID')
    user_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='用户 ID')
    claim_status: Mapped[int] = mapped_column(
        sa.SmallInteger,
        default=0,
        comment='领取状态(0 进行中 1 待审核 2 审核通过 3 审核拒绝 4 已发奖 5 已放弃 6 已撤销)',
    )
    claim_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='领取时间')
    expire_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='领取过期时间')
    submission_links: Mapped[list | None] = mapped_column(sa.JSON, default=None, comment='提交链接列表')
    submission_images: Mapped[list | None] = mapped_column(sa.JSON, default=None, comment='提交图片列表')
    submission_note: Mapped[str | None] = mapped_column(UniversalText, default=None, comment='提交说明')
    submit_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='提交时间')
    review_remark: Mapped[str | None] = mapped_column(sa.String(500), default=None, comment='审核备注')
    reviewed_by: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='审核人用户 ID')
    review_time: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='审核时间')
    reward_status: Mapped[int] = mapped_column(
        sa.SmallInteger,
        default=0,
        comment='奖励状态(0 未发放 1 已发放 2 发放失败 3 已撤销)',
    )
    granted_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='奖励发放时间')
    progress: Mapped[int] = mapped_column(default=0, comment='自动触发型任务的当前累计进度')
