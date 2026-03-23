#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class InviteRelation(Base):
    """邀请关系表"""

    __tablename__ = 'invite_relation'
    __table_args__ = (
        sa.UniqueConstraint('inviter_user_id', 'invitee_user_id', name='uq_invite_pair'),
        {'comment': '邀请关系表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    invite_code_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='关联邀请码 ID')
    inviter_user_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='邀请人用户 ID')
    invitee_user_id: Mapped[int] = mapped_column(sa.BigInteger, index=True, comment='被邀请人用户 ID')
    inviter_reward_status: Mapped[int] = mapped_column(default=0, comment='邀请人奖励状态(0 待发放 1 已发放 2 失败)')
    invitee_reward_status: Mapped[int] = mapped_column(default=0, comment='被邀请人奖励状态(0 待发放 1 已发放 2 失败)')
    channel: Mapped[str | None] = mapped_column(sa.String(32), default=None, comment='渠道来源')
    ip_address: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='被邀请人 IP 地址')
