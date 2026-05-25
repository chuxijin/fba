#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import JSON, BigInteger, Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, TimeZone
from backend.plugin.webhook.model.primary_key import webhook_id_column
from datetime import datetime


class WebhookEndpoint(Base):
    """Webhook 出站端点表"""

    __tablename__ = 'webhook_endpoint'

    id: Mapped[int] = webhook_id_column()
    uid: Mapped[str] = mapped_column(String(32), unique=True, comment='端点唯一标识')
    name: Mapped[str] = mapped_column(String(100), comment='端点名称')
    url: Mapped[str] = mapped_column(String(500), comment='目标 URL')
    secret: Mapped[str] = mapped_column(String(255), comment='签名密钥 (whsec_ 开头)')
    event_types: Mapped[list] = mapped_column(JSON, comment='订阅的事件类型列表')
    description: Mapped[str | None] = mapped_column(String(500), default=None, comment='描述')
    headers: Mapped[dict | None] = mapped_column(JSON, default=None, comment='自定义请求头')
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment='是否启用')
    failure_count: Mapped[int] = mapped_column(Integer, default=0, comment='连续失败次数')
    max_retries: Mapped[int] = mapped_column(Integer, default=5, comment='最大重试次数')
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30, comment='超时秒数')
    last_success_at: Mapped[datetime | None] = mapped_column(
        TimeZone, default=None, comment='最后成功时间'
    )
    last_failure_at: Mapped[datetime | None] = mapped_column(
        TimeZone, default=None, comment='最后失败时间'
    )
