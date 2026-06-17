#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Boolean, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, UniversalText
from backend.plugin.webhook.model.primary_key import webhook_id_column
from datetime import datetime


class WebhookEventLog(Base):
    """Webhook 入站事件日志表"""

    __tablename__ = 'webhook_event_log'

    id: Mapped[int] = webhook_id_column()
    uid: Mapped[str] = mapped_column(String(32), unique=True, comment='日志唯一标识')
    source: Mapped[str] = mapped_column(String(100), comment='事件来源 (github/stripe/generic)')
    event_type: Mapped[str] = mapped_column(String(200), comment='事件类型')
    payload: Mapped[str] = mapped_column(UniversalText, comment='原始请求体')
    event_id: Mapped[str | None] = mapped_column(String(100), index=True, default=None, comment='外部事件 ID (幂等)')
    headers: Mapped[dict | None] = mapped_column(JSON, default=None, comment='请求头 (脱敏后)')
    signature_valid: Mapped[bool] = mapped_column(Boolean, default=False, comment='签名验证结果')
    status: Mapped[int] = mapped_column(Integer, default=0, comment='状态 (0:received 1:processed 2:failed)')
    error_message: Mapped[str | None] = mapped_column(String(1000), default=None, comment='错误信息')
    processed_at: Mapped[datetime | None] = mapped_column(TimeZone, default=None, comment='处理时间')
    source_ip: Mapped[str | None] = mapped_column(String(45), default=None, comment='请求来源 IP')
