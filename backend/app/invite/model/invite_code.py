#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class InviteCode(Base):
    """邀请码表"""

    __tablename__ = 'invite_code'

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='持有人用户 ID')
    code: Mapped[str] = mapped_column(sa.String(64), unique=True, index=True, comment='邀请码')
    campaign_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, index=True, comment='活动 ID')
    channel: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='渠道(web/miniapp)')
    max_uses: Mapped[int] = mapped_column(default=0, comment='最大使用次数(0 不限)')
    used_count: Mapped[int] = mapped_column(default=0, comment='已使用次数')
    reward_rule_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, index=True, comment='奖励规则 ID')
    status: Mapped[int] = mapped_column(default=1, index=True, comment='状态(0 停用 1 启用)')
