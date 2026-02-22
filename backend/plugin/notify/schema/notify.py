#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CreateNotifyParam(BaseModel):
    """发送通知参数"""

    title: str = Field(description='通知标题', max_length=128)
    content: str = Field(description='通知内容')
    channels: list[str] | None = Field(default=None, description='指定渠道列表(为空则使用默认优先级)')
    options: dict[str, str] | None = Field(default=None, description='渠道扩展参数(如 Server 酱 tags)')


class CreateNotifyLog(BaseModel):
    """创建通知日志"""

    title: str = Field(description='通知标题')
    content: str = Field(description='通知内容')
    channel: str | None = Field(default=None, description='成功发送渠道')
    status: int = Field(default=0, description='发送状态')
    attempts: str | None = Field(default=None, description='各渠道尝试记录')
    error_msg: str | None = Field(default=None, description='最终错误信息')
    source: str | None = Field(default=None, description='触发来源')


class GetNotifyLogDetail(BaseModel):
    """通知日志详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='日志ID')
    title: str = Field(description='通知标题')
    content: str = Field(description='通知内容')
    channel: str | None = Field(default=None, description='成功发送渠道')
    status: int = Field(description='发送状态')
    attempts: str | None = Field(default=None, description='各渠道尝试记录')
    error_msg: str | None = Field(default=None, description='最终错误信息')
    source: str | None = Field(default=None, description='触发来源')
    created_time: datetime = Field(description='创建时间')


class NotifySendResult(BaseModel):
    """通知发送结果"""

    success: bool = Field(description='是否发送成功')
    channel: str | None = Field(default=None, description='成功渠道')
    log_id: int = Field(description='日志ID')
