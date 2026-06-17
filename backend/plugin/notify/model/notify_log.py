#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class NotifyLog(Base):
    """通知日志表"""

    __tablename__ = 'notify_log'
    __table_args__ = {'comment': '通知日志表'}

    id: Mapped[id_key] = mapped_column(init=False)
    title: Mapped[str] = mapped_column(String(128), comment='通知标题')
    content: Mapped[str] = mapped_column(Text, comment='通知内容')
    channel: Mapped[str | None] = mapped_column(String(32), default=None, comment='成功发送渠道')
    status: Mapped[int] = mapped_column(Integer, default=0, comment='发送状态(0:待发送 1:成功 2:全部失败)')
    attempts: Mapped[str | None] = mapped_column(Text, default=None, comment='各渠道尝试记录(JSON)')
    error_msg: Mapped[str | None] = mapped_column(Text, default=None, comment='最终错误信息')
    source: Mapped[str | None] = mapped_column(String(64), default=None, comment='触发来源(api/internal)')
