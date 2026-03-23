#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, id_key


class InviteRewardRule(Base):
    """邀请奖励规则表"""

    __tablename__ = 'invite_reward_rule'

    id: Mapped[id_key] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(sa.String(128), comment='规则名称')
    # 邀请人奖励
    inviter_reward_type: Mapped[str] = mapped_column(sa.String(32), comment='邀请人权益类型(vip/points/feature)')
    inviter_reward_data: Mapped[dict] = mapped_column(sa.JSON, comment='邀请人权益数据')
    # 被邀请人奖励
    invitee_reward_type: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='被邀请人权益类型')
    invitee_reward_data: Mapped[dict | None] = mapped_column(sa.JSON, default=None, comment='被邀请人权益数据')
    # 限制条件
    max_invites_per_user: Mapped[int] = mapped_column(default=0, comment='单用户最大邀请数(0 不限)')
    valid_from: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='生效时间')
    valid_to: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='失效时间')
    status: Mapped[int] = mapped_column(default=1, comment='状态(0 停用 1 启用)')
