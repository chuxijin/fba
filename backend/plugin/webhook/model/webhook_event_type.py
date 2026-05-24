#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Boolean, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base
from backend.plugin.webhook.model.primary_key import webhook_id_column


class WebhookEventType(Base):
    """Webhook 事件类型注册表"""

    __tablename__ = 'webhook_event_type'

    id: Mapped[int] = webhook_id_column()
    type_key: Mapped[str] = mapped_column(String(200), unique=True, comment='事件类型标识')
    category: Mapped[str] = mapped_column(String(50), comment='分类 (order/payment/user/system)')
    description: Mapped[str | None] = mapped_column(String(500), default=None, comment='描述')
    payload_schema: Mapped[dict | None] = mapped_column(JSON, default=None, comment='payload JSON Schema')
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment='是否启用')
