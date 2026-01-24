#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key
from backend.utils.timezone import timezone


class AgisoPushLog(Base):
    """阿奇索推送日志表"""

    __tablename__ = 'agiso_push_log'

    # 主键和必填字段（没有默认值的字段必须放在前面）
    id: Mapped[id_key] = mapped_column(init=False)
    push_type: Mapped[str] = mapped_column(String(50), comment='推送类型(payment:支付推送 delivery:发卡推送)')
    order_no: Mapped[str] = mapped_column(String(100), index=True, comment='订单编号')
    push_data: Mapped[str] = mapped_column(Text, comment='推送原始数据')

    # 有默认值的字段（必须放在后面）
    platform: Mapped[str | None] = mapped_column(String(50), default=None, comment='来源平台')
    process_status: Mapped[int] = mapped_column(
        default=0, comment='处理状态(0:待处理 1:处理成功 2:处理失败)'
    )
    process_result: Mapped[str | None] = mapped_column(Text, default=None, comment='处理结果')
    error_message: Mapped[str | None] = mapped_column(Text, default=None, comment='错误信息')
    retry_count: Mapped[int] = mapped_column(Integer, default=0, comment='重试次数')
    created_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), init=False, default_factory=timezone.now, comment='创建时间'
    )
    processed_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, comment='处理时间'
    )
