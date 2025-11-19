#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class BiliWorkSchemaBase(SchemaBase):
    """B 站作品基础模型"""

    work_id: str = Field(description='B 站作品 ID')
    title: str = Field(description='标题')
    work_type: str = Field(description='作品类型(video/dynamic/article/column)')
    aid: int | None = Field(None, description='视频 AID')
    url: str | None = Field(None, description='作品链接')
    view_count: int = Field(0, description='播放量/阅读量')
    like_count: int = Field(0, description='点赞数')
    comment_count: int = Field(0, description='评论数')
    coin_count: int = Field(0, description='投币数')
    share_count: int = Field(0, description='分享数')
    favorite_count: int = Field(0, description='收藏数')
    mid: str | None = Field(None, description='所属 B 站用户 MID')


class CreateBiliWorkParam(BiliWorkSchemaBase):
    """创建 B 站作品参数"""


class UpdateBiliWorkParam(SchemaBase):
    """更新 B 站作品参数"""

    work_id: str | None = Field(None, description='B 站作品 ID')
    title: str | None = Field(None, description='标题')
    work_type: str | None = Field(None, description='作品类型')
    aid: int | None = Field(None, description='视频 AID')
    url: str | None = Field(None, description='作品链接')
    view_count: int | None = Field(None, description='播放量/阅读量')
    like_count: int | None = Field(None, description='点赞数')
    comment_count: int | None = Field(None, description='评论数')
    coin_count: int | None = Field(None, description='投币数')
    share_count: int | None = Field(None, description='分享数')
    favorite_count: int | None = Field(None, description='收藏数')
    mid: str | None = Field(None, description='所属 B 站用户 MID')


class GetBiliWorkDetail(BiliWorkSchemaBase):
    """B 站作品详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='ID')
    publish_time: datetime | None = Field(None, description='发布时间')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')
