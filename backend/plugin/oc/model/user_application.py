#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

import sqlalchemy as sa

from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.common.model import DataClassBase, DateTimeMixin, id_key
from backend.plugin.oc.model.company import OCRecruitAnnouncement


class UserApplication(DataClassBase, DateTimeMixin):
    """用户投递记录表"""

    __tablename__ = 'oc_user_application'

    id: Mapped[id_key] = mapped_column(init=False)
    user_id: Mapped[int] = mapped_column(
        sa.BigInteger, sa.ForeignKey('sys_user.id', ondelete='CASCADE'), index=True, comment='用户ID'
    )
    announcement_id: Mapped[int] = mapped_column(
        sa.BigInteger,
        sa.ForeignKey('oc_recruit_announcement.id', ondelete='CASCADE'),
        index=True,
        comment='公告ID',
    )
    application_status: Mapped[str] = mapped_column(sa.String(32), default='未投递', comment='投递状态')
    applied_at: Mapped[datetime | None] = mapped_column(sa.DateTime, default=None, comment='投递时间')
    remark: Mapped[str | None] = mapped_column(sa.Text, default=None, comment='备注')

    announcement: Mapped[OCRecruitAnnouncement] = relationship(init=False, lazy='noload')
