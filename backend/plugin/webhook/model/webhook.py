#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import JSON, TEXT, String
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class Webhook(Base):
    """Webhook事件记录表"""

    __tablename__ = 'sys_webhook'

    id: Mapped[id_key] = mapped_column(init=False)
    event_type: Mapped[str] = mapped_column(String(100), comment='事件类型')
    source: Mapped[str] = mapped_column(String(500), comment='事件来源')
    payload: Mapped[str] = mapped_column(LONGTEXT().with_variant(TEXT, 'postgresql'), comment='事件数据')
    webhook_url: Mapped[str | None] = mapped_column(String(500), default=None, comment='Webhook URL')
    headers: Mapped[dict | None] = mapped_column(JSON, default=None, comment='请求头信息')
    error_message: Mapped[str | None] = mapped_column(String(1000), default=None, comment='错误信息')
    processed_at: Mapped[str | None] = mapped_column(String(19), default=None, comment='处理时间')
    status: Mapped[int] = mapped_column(default=1, comment='处理状态（0：失败、1：成功、2：待处理）')
    retry_count: Mapped[int] = mapped_column(default=0, comment='重试次数') 