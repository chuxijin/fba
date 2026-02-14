#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CreatePushLog(BaseModel):
    """创建推送日志"""

    order_no: str = Field(description='订单编号')
    order_status: str = Field(description='订单状态')
    buyer_nick: str = Field(description='买家昵称')
    payment: str = Field(description='支付金额')
    raw_json: str = Field(description='推送原始JSON数据')
    platform: str | None = Field(default=None, description='来源平台')
    push_timestamp: str | None = Field(default=None, description='推送时间戳')
    push_type: int | None = Field(default=None, description='推送类型')
    seller_nick: str | None = Field(default=None, description='卖家昵称')
    seller_id: str | None = Field(default=None, description='卖家ID')
    buyer_id: str | None = Field(default=None, description='买家ID')
    trade_type: str | None = Field(default=None, description='交易类型')


class GetPushLogDetail(BaseModel):
    """推送日志详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='日志ID')
    platform: str | None = Field(default=None, description='来源平台')
    push_timestamp: str | None = Field(default=None, description='推送时间戳')
    push_type: int | None = Field(default=None, description='推送类型')
    order_no: str = Field(description='订单编号')
    order_status: str = Field(description='订单状态')
    seller_nick: str | None = Field(default=None, description='卖家昵称')
    seller_id: str | None = Field(default=None, description='卖家ID')
    buyer_nick: str = Field(description='买家昵称')
    buyer_id: str | None = Field(default=None, description='买家ID')
    payment: str = Field(description='支付金额')
    trade_type: str | None = Field(default=None, description='交易类型')
    process_status: int = Field(description='处理状态')
    process_result: str | None = Field(default=None, description='处理结果')
    raw_json: str = Field(description='推送原始JSON数据')
    created_time: datetime = Field(description='创建时间')
