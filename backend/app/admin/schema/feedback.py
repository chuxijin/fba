#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field

from backend.app.admin.model.feedback import FeedbackStatus, FeedbackType
from backend.common.schema import SchemaBase

FeedbackTypeLiteral = Literal[
    FeedbackType.BUG,
    FeedbackType.CONTENT_ERROR,
    FeedbackType.PRODUCT_SUGGESTION,
    FeedbackType.FEATURE_REQUEST,
    FeedbackType.EXPERIENCE,
    FeedbackType.OTHER,
]
FeedbackStatusLiteral = Literal[
    FeedbackStatus.PENDING,
    FeedbackStatus.PROCESSING,
    FeedbackStatus.RESOLVED,
    FeedbackStatus.REJECTED,
]


class CreateFeedbackParam(SchemaBase):
    """创建反馈参数"""

    feedback_type: FeedbackTypeLiteral = Field(default=FeedbackType.OTHER, description='反馈类型')
    content: str = Field(description='反馈内容')
    contact: str | None = Field(default=None, description='联系方式')
    images: list[str] | None = Field(default=None, description='图片列表')
    source_app: str | None = Field(default=None, description='来源应用')
    source_platform: str | None = Field(default=None, description='来源平台')
    page_path: str | None = Field(default=None, description='页面路径')
    target_type: str | None = Field(default=None, description='关联目标类型')
    target_id: str | None = Field(default=None, description='关联目标 ID')
    target_text: str | None = Field(default=None, description='关联目标描述')


class UpdateFeedbackParam(SchemaBase):
    """更新反馈参数"""

    status: FeedbackStatusLiteral | None = Field(default=None, description='处理状态')
    reply_content: str | None = Field(default=None, description='处理回复')


class DeleteFeedbackParam(SchemaBase):
    """删除反馈参数"""

    ids: list[int] = Field(description='反馈 ID 列表')


class FeedbackQueryParam(SchemaBase):
    """反馈查询参数"""

    feedback_type: FeedbackTypeLiteral | None = Field(default=None, description='反馈类型')
    status: FeedbackStatusLiteral | None = Field(default=None, description='处理状态')
    keyword: str | None = Field(default=None, description='内容关键词')
    contact: str | None = Field(default=None, description='联系方式')
    source_app: str | None = Field(default=None, description='来源应用')
    source_platform: str | None = Field(default=None, description='来源平台')
    target_type: str | None = Field(default=None, description='关联目标类型')
    is_read: bool | None = Field(default=None, description='是否已读')


class GetMyFeedbackItem(SchemaBase):
    """我的反馈列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='反馈 ID')
    feedback_type: FeedbackTypeLiteral = Field(description='反馈类型')
    content: str = Field(description='反馈内容')
    images: list[str] | None = Field(default=None, description='图片列表')
    target_text: str | None = Field(default=None, description='关联目标描述')
    status: FeedbackStatusLiteral = Field(description='处理状态')
    reply_content: str | None = Field(default=None, description='处理回复')
    handled_time: datetime | None = Field(default=None, description='处理时间')
    created_time: datetime = Field(description='提交时间')


class GetFeedbackDetail(SchemaBase):
    """反馈详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='反馈 ID')
    feedback_type: FeedbackTypeLiteral = Field(description='反馈类型')
    content: str = Field(description='反馈内容')
    contact: str | None = Field(default=None, description='联系方式')
    images: list[str] | None = Field(default=None, description='图片列表')
    source_app: str | None = Field(default=None, description='来源应用')
    source_platform: str | None = Field(default=None, description='来源平台')
    page_path: str | None = Field(default=None, description='页面路径')
    target_type: str | None = Field(default=None, description='关联目标类型')
    target_id: str | None = Field(default=None, description='关联目标 ID')
    target_text: str | None = Field(default=None, description='关联目标描述')
    status: FeedbackStatusLiteral = Field(description='处理状态')
    reply_content: str | None = Field(default=None, description='处理回复')
    read_time: datetime | None = Field(default=None, description='首次查看时间')
    handled_by: int | None = Field(default=None, description='处理人 ID')
    handled_time: datetime | None = Field(default=None, description='处理时间')
    ip_address: str | None = Field(default=None, description='IP 地址')
    user_agent: str | None = Field(default=None, description='用户代理')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(default=None, description='更新时间')
