#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class WebhookConfig(Base):
    """Webhook配置表"""

    __tablename__ = 'sys_webhook_config'

    id: Mapped[id_key] = mapped_column(init=False)
    name: Mapped[str] = mapped_column(String(100), comment='配置名称')
    endpoint_url: Mapped[str] = mapped_column(String(500), comment='允许的发送方域名或目标接收URL')
    secret_key: Mapped[str | None] = mapped_column(String(255), default=None, comment='密钥用于签名验证')
    required_headers: Mapped[dict | None] = mapped_column(JSON, default=None, comment='必需的请求头')
    allowed_event_types: Mapped[list | None] = mapped_column(JSON, default=None, comment='允许的事件类型')
    is_active: Mapped[bool] = mapped_column(default=True, comment='是否启用') 