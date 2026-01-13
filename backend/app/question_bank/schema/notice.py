#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class NoticeSchemaBase(SchemaBase):
    """通知栏基础"""

    content: str = Field(description='通知内容')
    notice_type: str = Field(default='info', description='类型: info/warning/success')
    link_url: str | None = Field(None, description='跳转链接')
    status: int = Field(default=1, description='状态: 0=禁用, 1=启用')
    start_time: datetime | None = Field(None, description='开始时间')
    end_time: datetime | None = Field(None, description='结束时间')
    scene: str = Field(default='home', description='展示场景: home/practice/study 等')
    sort: int = Field(default=0, description='排序（数字越小越靠前）')
    is_scrollable: bool = Field(default=True, description='是否滚动')


class GetNoticeDetail(NoticeSchemaBase):
    """通知详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='通知 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetActiveNotice(SchemaBase):
    """前端展示通知"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='通知 ID')
    content: str = Field(description='通知内容')
    notice_type: str = Field(description='类型')
    link_url: str | None = Field(None, description='跳转链接')
    is_scrollable: bool = Field(description='是否滚动')


class CreateNoticeParam(NoticeSchemaBase):
    """创建通知参数"""


class UpdateNoticeParam(NoticeSchemaBase):
    """更新通知参数"""
