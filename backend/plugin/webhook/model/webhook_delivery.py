#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import BigInteger, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone, UniversalText
from backend.plugin.webhook.model.primary_key import webhook_id_column
from datetime import datetime


class WebhookDelivery(Base):
    """Webhook 投递记录表"""

    __tablename__ = 'webhook_delivery'

    id: Mapped[int] = webhook_id_column()
    uid: Mapped[str] = mapped_column(String(32), unique=True, comment='投递唯一标识')
    endpoint_id: Mapped[int] = mapped_column(BigInteger, index=True, comment='端点 ID')
    event_id: Mapped[str] = mapped_column(String(100), index=True, comment='事件 ID (幂等 key)')
    event_type: Mapped[str] = mapped_column(String(200), comment='事件类型')
    payload: Mapped[str] = mapped_column(UniversalText, comment='完整 CloudEvents JSON')
    signature: Mapped[str | None] = mapped_column(String(500), default=None, comment='生成的签名')
    timestamp: Mapped[int | None] = mapped_column(BigInteger, default=None, comment='签名时间戳')
    status: Mapped[int] = mapped_column(Integer, default=0, comment='投递状态 (0:pending 1:success 2:failed 3:retrying)')
    response_code: Mapped[int | None] = mapped_column(Integer, default=None, comment='HTTP 响应码')
    response_body: Mapped[str | None] = mapped_column(Text, default=None, comment='响应体 (截断 10KB)')
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, comment='已尝试次数')
    next_retry_at: Mapped[datetime | None] = mapped_column(
        TimeZone, default=None, comment='下次重试时间'
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        TimeZone, default=None, comment='完成时间'
    )
