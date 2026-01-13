#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class BannerSchemaBase(SchemaBase):
    """轮播图基础"""

    title: str = Field(description='标题')
    image_url: str = Field(description='图片 URL')
    link_type: str = Field(default='none', description='链接类型: none/url/miniprogram')
    link_url: str | None = Field(None, description='跳转链接')
    scene: str = Field(default='home', description='展示场景: home/practice/study 等')
    sort: int = Field(default=0, description='排序（数字越小越靠前）')
    status: int = Field(default=1, description='状态: 0=禁用, 1=启用')
    start_time: datetime | None = Field(None, description='开始时间')
    end_time: datetime | None = Field(None, description='结束时间')


class GetBannerDetail(BannerSchemaBase):
    """轮播图详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='轮播图 ID')
    click_count: int = Field(description='点击次数')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetActiveBanner(SchemaBase):
    """前端展示轮播图"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='轮播图 ID')
    title: str = Field(description='标题')
    image_url: str = Field(description='图片 URL')
    link_type: str = Field(description='链接类型')
    link_url: str | None = Field(None, description='跳转链接')


class CreateBannerParam(BannerSchemaBase):
    """创建轮播图参数"""


class UpdateBannerParam(BannerSchemaBase):
    """更新轮播图参数"""
