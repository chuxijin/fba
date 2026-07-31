#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field

from backend.app.admin.model.message import MessageTargetType, MessageType
from backend.common.schema import SchemaBase

MessageTargetTypeLiteral = Literal[
    MessageTargetType.ALL,
    MessageTargetType.USER,
    MessageTargetType.ROLE,
]
MessageTypeLiteral = Literal[
    MessageType.SYSTEM,
    MessageType.UPDATE,
    MessageType.MAINTENANCE,
    MessageType.PERSONAL,
]


class CreateMessageParam(SchemaBase):
    """创建消息参数"""

    title: str = Field(description='标题')
    content: str = Field(description='内容')
    target_type: MessageTargetTypeLiteral = Field(default=MessageTargetType.ALL, description='目标类型')
    user_id: int | None = Field(default=None, description='目标用户 ID（target_type=user 时必填）')
    role_id: int | None = Field(default=None, description='目标角色 ID（target_type=role 时必填）')
    message_type: MessageTypeLiteral = Field(default=MessageType.SYSTEM, description='消息类型')
    biz_source: str | None = Field(default=None, description='来源模块')
    biz_id: str | None = Field(default=None, description='来源业务对象 ID')
    link_url: str | None = Field(default=None, description='跳转链接')
    payload: dict | None = Field(default=None, description='扩展数据')
    publish_time: datetime | None = Field(default=None, description='发布时间')
    expire_time: datetime | None = Field(default=None, description='过期时间')


class UpdateMessageParam(SchemaBase):
    """更新消息参数"""

    title: str | None = Field(default=None, description='标题')
    content: str | None = Field(default=None, description='内容')
    target_type: MessageTargetTypeLiteral | None = Field(default=None, description='目标类型')
    user_id: int | None = Field(default=None, description='目标用户 ID')
    role_id: int | None = Field(default=None, description='目标角色 ID')
    message_type: MessageTypeLiteral | None = Field(default=None, description='消息类型')
    link_url: str | None = Field(default=None, description='跳转链接')
    payload: dict | None = Field(default=None, description='扩展数据')
    status: int | None = Field(default=None, description='状态: 0=禁用, 1=启用')
    publish_time: datetime | None = Field(default=None, description='发布时间')
    expire_time: datetime | None = Field(default=None, description='过期时间')


class DeleteMessageParam(SchemaBase):
    """删除消息参数"""

    ids: list[int] = Field(description='消息 ID 列表')


class MessageQueryParam(SchemaBase):
    """消息查询参数"""

    message_type: MessageTypeLiteral | None = Field(default=None, description='消息类型')
    target_type: MessageTargetTypeLiteral | None = Field(default=None, description='目标类型')
    status: int | None = Field(default=None, description='状态')
    keyword: str | None = Field(default=None, description='标题或内容关键词')
    biz_source: str | None = Field(default=None, description='来源模块')


class PublishMessageParam(SchemaBase):
    """内部生产者发布消息参数"""

    title: str = Field(description='标题')
    content: str = Field(description='内容')
    target_type: MessageTargetTypeLiteral = Field(default=MessageTargetType.ALL, description='目标类型')
    user_id: int | None = Field(default=None, description='目标用户 ID')
    role_id: int | None = Field(default=None, description='目标角色 ID')
    message_type: MessageTypeLiteral = Field(default=MessageType.SYSTEM, description='消息类型')
    biz_source: str | None = Field(default=None, description='来源模块')
    biz_id: str | None = Field(default=None, description='来源业务对象 ID')
    link_url: str | None = Field(default=None, description='跳转链接')
    payload: dict | None = Field(default=None, description='扩展数据')
    expire_time: datetime | None = Field(default=None, description='过期时间')


class GetMessageDetail(SchemaBase):
    """消息详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='消息 ID')
    title: str = Field(description='标题')
    content: str = Field(description='内容')
    target_type: MessageTargetTypeLiteral = Field(description='目标类型')
    user_id: int | None = Field(default=None, description='目标用户 ID')
    role_id: int | None = Field(default=None, description='目标角色 ID')
    message_type: MessageTypeLiteral = Field(description='消息类型')
    biz_source: str | None = Field(default=None, description='来源模块')
    biz_id: str | None = Field(default=None, description='来源业务对象 ID')
    sender_id: int | None = Field(default=None, description='发送人 ID')
    link_url: str | None = Field(default=None, description='跳转链接')
    payload: dict | None = Field(default=None, description='扩展数据')
    status: int = Field(description='状态')
    publish_time: datetime | None = Field(default=None, description='发布时间')
    expire_time: datetime | None = Field(default=None, description='过期时间')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(default=None, description='更新时间')


class GetMyMessageItem(SchemaBase):
    """我的消息列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='消息 ID')
    title: str = Field(description='标题')
    content: str = Field(description='内容')
    message_type: MessageTypeLiteral = Field(description='消息类型')
    target_type: MessageTargetTypeLiteral = Field(description='目标类型')
    biz_source: str | None = Field(default=None, description='来源模块')
    biz_id: str | None = Field(default=None, description='来源业务对象 ID')
    link_url: str | None = Field(default=None, description='跳转链接')
    payload: dict | None = Field(default=None, description='扩展数据')
    publish_time: datetime | None = Field(default=None, description='发布时间')
    created_time: datetime = Field(description='创建时间')
    is_read: bool = Field(default=False, description='是否已读')
    read_time: datetime | None = Field(default=None, description='读取时间')
