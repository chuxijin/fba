#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class MyDrivePublicResourceListItem(SchemaBase):
    """公开资源列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='资源 ID')
    category_id: int = Field(description='分类 ID')
    category_name: str | None = Field(default=None, description='分类名称')
    title: str = Field(description='资源标题')
    description: str = Field(description='资源介绍')
    org_name: str = Field(description='机构或老师名称')
    resource_type: str = Field(description='资源类型')
    hot: int = Field(description='热度')
    created_time: datetime = Field(description='创建时间')


class MyDrivePublicResourceDetail(MyDrivePublicResourceListItem):
    """公开资源详情"""

    images: list[str] = Field(description='资源图片')
    share_url: str = Field(description='分享链接')
    provider: str = Field(description='网盘驱动标识')
    file_size: int | None = Field(default=None, description='文件大小')
    updated_time: datetime | None = Field(description='更新时间')


class MyDrivePublicResourceClickResult(SchemaBase):
    """公开资源点击结果"""

    view_count: int = Field(description='浏览量')
