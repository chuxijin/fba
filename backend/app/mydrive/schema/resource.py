#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class MyDriveResourceShareParam(SchemaBase):
    """资源分享参数"""

    provider: str = Field(min_length=1, max_length=64, description='网盘驱动标识')
    account_id: int | None = Field(default=None, gt=0, description='网盘账户 ID')
    source_type: str = Field(default='imported_link', max_length=32, description='来源类型')
    source_ref: dict = Field(default_factory=dict, description='来源定位信息')
    share_url: str = Field(min_length=1, max_length=1000, description='分享链接')
    share_id: str = Field(default='', max_length=255, description='分享 ID')
    share_key: str = Field(default='', max_length=255, description='分享唯一标识')
    extract_code: str = Field(default='', max_length=50, description='提取码')
    share_title: str = Field(default='', max_length=255, description='网盘分享标题')
    share_status: str = Field(default='unknown', max_length=32, description='分享状态')
    share_audit_status: str = Field(default='unknown', max_length=32, description='分享审核状态')
    share_expired_at: datetime | None = Field(default=None, description='分享过期时间')
    expires_in_days: int = Field(default=0, ge=0, description='有效期天数')
    share_meta: dict = Field(default_factory=dict, description='分享原始信息')
    file_id: str = Field(default='', max_length=255, description='文件 ID')
    file_name: str = Field(default='', max_length=512, description='文件名称')
    file_path: str = Field(default='', max_length=1024, description='文件路径')
    is_directory: bool = Field(default=False, description='是否目录')
    file_size: int | None = Field(default=None, ge=0, description='文件大小')
    file_type: str = Field(default='', max_length=50, description='文件类型')


class CreateMyDriveResourceParam(SchemaBase):
    """创建资源参数"""

    category_id: int = Field(gt=0, description='分类 ID')
    title: str = Field(min_length=1, max_length=255, description='资源标题')
    resource_type: str = Field(min_length=1, max_length=50, description='资源类型')
    description: str = Field(default='', description='资源介绍')
    images: list = Field(default_factory=list, description='资源图片列表')
    org_name: str = Field(default='', max_length=100, description='机构或老师名称')
    tags: list[str] = Field(default_factory=list, description='资源标签')
    content: str = Field(default='', description='搜索内容')
    status: str = Field(default='enabled', max_length=32, description='状态')
    audit_status: str = Field(default='approved', max_length=32, description='审核状态')
    temp_policy: int = Field(default=0, ge=0, le=3, description='临时策略')
    sort: int = Field(default=0, description='排序')
    resource_expired_at: datetime | None = Field(default=None, description='资源过期时间')
    share: MyDriveResourceShareParam = Field(description='资源分享信息')


class UpdateMyDriveResourceParam(SchemaBase):
    """更新资源参数"""

    category_id: int | None = Field(default=None, gt=0, description='分类 ID')
    title: str | None = Field(default=None, min_length=1, max_length=255, description='资源标题')
    resource_type: str | None = Field(default=None, min_length=1, max_length=50, description='资源类型')
    description: str | None = Field(default=None, description='资源介绍')
    images: list | None = Field(default=None, description='资源图片列表')
    org_name: str | None = Field(default=None, max_length=100, description='机构或老师名称')
    tags: list[str] | None = Field(default=None, description='资源标签')
    content: str | None = Field(default=None, description='搜索内容')
    status: str | None = Field(default=None, max_length=32, description='状态')
    audit_status: str | None = Field(default=None, max_length=32, description='审核状态')
    temp_policy: int | None = Field(default=None, ge=0, le=3, description='临时策略')
    sort: int | None = Field(default=None, description='排序')
    resource_expired_at: datetime | None = Field(default=None, description='资源过期时间')
    share: MyDriveResourceShareParam | None = Field(default=None, description='资源分享信息')


class GetMyDriveResourceShareDetail(MyDriveResourceShareParam):
    """资源分享详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='分享 ID')
    resource_id: int = Field(description='资源 ID')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(description='更新时间')


class GetMyDriveResourceDetail(SchemaBase):
    """资源详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='资源 ID')
    owner_id: int = Field(description='所属用户 ID')
    category_id: int = Field(description='分类 ID')
    title: str = Field(description='资源标题')
    resource_type: str = Field(description='资源类型')
    description: str = Field(description='资源介绍')
    images: list = Field(description='资源图片列表')
    org_name: str = Field(description='机构或老师名称')
    tags: list[str] = Field(description='资源标签')
    content: str = Field(description='搜索内容')
    view_count: int = Field(description='平台浏览量')
    search_count: int = Field(description='平台搜索次数')
    hot: int = Field(description='热点值')
    last_viewed_at: datetime | None = Field(description='最近浏览时间')
    last_searched_at: datetime | None = Field(description='最近搜索时间')
    status: str = Field(description='状态')
    audit_status: str = Field(description='审核状态')
    temp_policy: int = Field(description='临时策略')
    sort: int = Field(description='排序')
    resource_expired_at: datetime | None = Field(description='资源过期时间')
    share: GetMyDriveResourceShareDetail | None = Field(default=None, description='资源分享信息')
    created_by: int = Field(description='创建者')
    updated_by: int | None = Field(description='更新者')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(description='更新时间')


class GetMyDriveResourceListParam(SchemaBase):
    """资源列表参数"""

    category_id: int | None = Field(default=None, description='分类 ID')
    resource_type: str | None = Field(default=None, description='资源类型')
    provider: str | None = Field(default=None, description='网盘驱动标识')
    status: str | None = Field(default=None, description='状态')
    audit_status: str | None = Field(default=None, description='审核状态')
    share_status: str | None = Field(default=None, description='分享状态')
    keyword: str | None = Field(default=None, description='关键词')
    sort_by: str = Field(default='created_time', description='排序字段')
    sort_order: str = Field(default='desc', description='排序方向')


class GetMyDriveResourceViewTrendParam(SchemaBase):
    """浏览趋势参数"""

    start_time: datetime | None = Field(default=None, description='开始时间')
    end_time: datetime | None = Field(default=None, description='结束时间')


class GetMyDriveResourceViewHistoryDetail(SchemaBase):
    """浏览历史详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='记录 ID')
    resource_id: int = Field(description='资源 ID')
    view_count: int = Field(description='当时浏览量')
    record_time: datetime = Field(description='记录时间')


class GetMyDriveResourceStatistics(SchemaBase):
    """资源统计"""

    total_count: int = Field(description='总资源数')
    active_count: int = Field(description='启用资源数')
    total_views: int = Field(description='总浏览量')
    total_searches: int = Field(description='总搜索次数')
    total_hot: int = Field(description='总热度')
