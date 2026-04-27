#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any, Literal

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase

MessageTargetType = Literal['all', 'user']
MessageStatus = Literal[0, 1]


class UserMessageSchemaBase(SchemaBase):
    """用户消息基础"""

    target_type: MessageTargetType = Field(default='all', description='目标类型')
    user_id: int | None = Field(None, gt=0, description='用户 ID')
    title: str = Field(min_length=1, max_length=128, description='标题')
    content: str = Field(min_length=1, description='内容')
    message_type: str = Field(default='system', max_length=32, description='消息类型')
    link_url: str | None = Field(None, max_length=500, description='跳转链接')
    payload: dict[str, Any] | None = Field(None, description='扩展数据')
    status: MessageStatus = Field(default=1, description='状态')
    publish_time: datetime | None = Field(None, description='发布时间')
    expire_time: datetime | None = Field(None, description='过期时间')


class CreateUserMessageParam(UserMessageSchemaBase):
    """创建用户消息"""


class UpdateUserMessageParam(UserMessageSchemaBase):
    """更新用户消息"""


class GetUserMessageDetail(UserMessageSchemaBase):
    """用户消息详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='消息 ID')
    read_time: datetime | None = Field(None, description='已读时间')
    is_read: bool = Field(default=False, description='是否已读')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetUserMessageListItem(SchemaBase):
    """用户消息列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='消息 ID')
    target_type: MessageTargetType = Field(description='目标类型')
    title: str = Field(description='标题')
    content: str = Field(description='内容')
    message_type: str = Field(description='消息类型')
    link_url: str | None = Field(None, description='跳转链接')
    payload: dict[str, Any] | None = Field(None, description='扩展数据')
    publish_time: datetime | None = Field(None, description='发布时间')
    expire_time: datetime | None = Field(None, description='过期时间')
    read_time: datetime | None = Field(None, description='已读时间')
    is_read: bool = Field(default=False, description='是否已读')


class UserMessageUnreadCount(SchemaBase):
    """未读消息数"""

    count: int = Field(ge=0, description='未读数量')
