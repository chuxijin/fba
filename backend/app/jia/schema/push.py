#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pydantic import Field

from backend.common.schema import SchemaBase


class PushMessageParam(SchemaBase):
    """推送消息参数"""

    title: str = Field(description='通知标题')
    body: str = Field(description='通知内容')
    data: dict | None = Field(None, description='额外数据')


class PushToUserParam(PushMessageParam):
    """推送给指定用户"""

    user_id: int = Field(description='用户 ID')


class PushToDeviceParam(PushMessageParam):
    """推送给指定设备"""

    fcm_token: str = Field(description='FCM Token')


class PushToAllParam(PushMessageParam):
    """推送给所有用户"""

    pass


class PushResult(SchemaBase):
    """推送结果"""

    success: bool = Field(description='是否成功')
    message_id: str | None = Field(None, description='消息 ID')
    error: str | None = Field(None, description='错误信息')
