#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class CmsSlotLog(Base):
    """内容运营位行为流水表"""

    __tablename__ = 'cms_slot_log'
    __table_args__ = (
        sa.Index('idx_cms_slot_log_freq', 'slot_id', 'user_id', 'action'),
        sa.Index('idx_cms_slot_log_time', 'slot_id', 'created_time'),
        {'comment': '内容运营位行为流水表'},
    )

    id: Mapped[id_key] = mapped_column(init=False)
    slot_id: Mapped[int] = mapped_column(sa.BigInteger, comment='关联运营位 ID')
    action: Mapped[int] = mapped_column(sa.SmallInteger, comment='行为类型(0 曝光 1 点击 2 关闭)')
    user_id: Mapped[int | None] = mapped_column(sa.BigInteger, default=None, comment='用户 ID(未登录可空)')
    scene: Mapped[str | None] = mapped_column(sa.String(64), default=None, comment='触发场景')
