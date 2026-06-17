#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class AgisoPushLog(Base):
    """阿奇索推送日志表"""

    __tablename__ = 'agiso_push_log'
    __table_args__ = (
        UniqueConstraint('order_no', 'push_type', name='uq_agiso_push_log_order_no_push_type'),
        {'comment': '阿奇索推送日志表'},
    )

    # 主键
    id: Mapped[id_key] = mapped_column(init=False)

    # 必填字段（无默认值，放前面）
    order_no: Mapped[str] = mapped_column(String(100), index=True, comment='订单编号(Tid/orderId)')
    raw_json: Mapped[str] = mapped_column(Text, comment='推送原始JSON数据')

    # 有默认值的字段（放后面）
    order_status: Mapped[str | None] = mapped_column(String(100), default=None, comment='订单状态')
    buyer_nick: Mapped[str | None] = mapped_column(String(100), default=None, comment='买家昵称')
    payment: Mapped[str | None] = mapped_column(String(50), default=None, comment='支付金额')
    platform: Mapped[str | None] = mapped_column(String(50), default=None, comment='来源平台(fromPlatform)')
    push_timestamp: Mapped[str | None] = mapped_column(String(50), default=None, comment='推送时间戳(timestamp)')
    push_type: Mapped[int | None] = mapped_column(
        Integer, default=None, comment='推送类型(aopic) 2097152:买家付款 2048:自动发货成功'
    )
    seller_nick: Mapped[str | None] = mapped_column(String(100), default=None, comment='卖家昵称')
    seller_id: Mapped[str | None] = mapped_column(String(200), default=None, comment='卖家ID')
    buyer_id: Mapped[str | None] = mapped_column(String(200), default=None, comment='买家ID')
    trade_type: Mapped[str | None] = mapped_column(String(50), default=None, comment='交易类型')
    goods_name: Mapped[str | None] = mapped_column(String(500), default=None, comment='商品名称(小红书GoodsName)')
    spec_name: Mapped[str | None] = mapped_column(String(500), default=None, comment='规格名称(小红书SpecName)')
    process_status: Mapped[int] = mapped_column(Integer, default=0, comment='处理状态(0:待处理 1:处理成功 2:处理失败)')
    process_result: Mapped[str | None] = mapped_column(Text, default=None, comment='处理结果')
