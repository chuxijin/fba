#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import datetime

from pydantic import Field

from backend.common.schema import SchemaBase


class SocialWorkMetricBase(SchemaBase):
    """作品数据基础 schema"""

    work_id: int = Field(..., description='作品ID')
    view_count: int = Field(0, description='浏览量')
    like_count: int = Field(0, description='点赞数')
    favorite_count: int = Field(0, description='收藏数')
    comment_count: int = Field(0, description='评论数')
    share_count: int = Field(0, description='转发/分享数')
    record_time: datetime | None = Field(None, description='记录时间')


class CreateSocialWorkMetricParam(SchemaBase):
    """创建作品数据参数"""

    work_id: int = Field(..., description='作品ID')
    view_count: int = Field(0, description='浏览量')
    like_count: int = Field(0, description='点赞数')
    favorite_count: int = Field(0, description='收藏数')
    comment_count: int = Field(0, description='评论数')
    record_time: datetime | None = Field(None, description='记录时间')
    share_count: int = Field(0, description='转发/分享数')


class UpdateSocialWorkMetricParam(SchemaBase):
    """更新作品数据参数"""

    view_count: int | None = Field(None, description='浏览量')
    like_count: int | None = Field(None, description='点赞数')
    favorite_count: int | None = Field(None, description='收藏数')
    comment_count: int | None = Field(None, description='评论数')
    record_time: datetime | None = Field(None, description='记录时间')
    share_count: int | None = Field(None, description='转发/分享数')


class GetSocialWorkMetricDetail(SchemaBase):
    """作品数据详情"""

    id: int = Field(..., description='主键 ID')
    work_id: int = Field(..., description='作品ID')
    view_count: int = Field(..., description='浏览量')
    like_count: int = Field(..., description='点赞数')
    favorite_count: int = Field(..., description='收藏数')
    comment_count: int = Field(..., description='评论数')
    share_count: int = Field(..., description='转发/分享数')
    record_time: datetime = Field(..., description='记录时间')
    created_time: datetime | None = Field(None, description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class SocialWorkTrendPoint(SchemaBase):
    """作品趋势点"""

    record_time: datetime = Field(..., description='记录时间')
    view_count: int = Field(..., description='浏览量')
    like_count: int = Field(..., description='点赞数')
    favorite_count: int = Field(..., description='收藏数')
    comment_count: int = Field(..., description='评论数')
    share_count: int = Field(..., description='转发/分享数')
