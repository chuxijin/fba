#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from decimal import Decimal

from pydantic import ConfigDict, Field
from pydantic.types import JsonValue

from backend.app.coulddrive.schema.enum import DriveType
from backend.common.schema import SchemaBase


class ResourceBase(SchemaBase):
    """资源基础 schema"""

    category_id: int = Field(description='分类 ID')
    resource_type: str = Field(description='资源类型')
    url: str = Field(description='链接')
    url_type: DriveType = Field(description='链接类型')

    remark: str | None = Field(None, description='资源标题')
    org_name: str | None = Field(None, description='机构或老师名称')
    resource_intro: str | None = Field(None, description='资源介绍')
    resource_image: JsonValue | None = Field(None, description='资源图片 JSON')
    extract_code: str | None = Field(None, description='提取码')
    is_temp_file: int = Field(0, ge=0, le=3, description='临时处理模式(0无操作 1定时删除 2定时刷新 3定时更新)')
    price: Decimal | None = Field(None, description='价格')
    suggested_price: Decimal | None = Field(None, description='建议价格')
    sort: int = Field(0, description='排序')

    title: str | None = Field(None, description='分享标题')
    share_id: str | None = Field(None, description='分享 ID')
    pwd_id: str | None = Field(None, description='密码 ID')
    expired_type: int = Field(0, description='过期类型(0永久 1定时)')
    view_count: int = Field(0, description='浏览量')
    expired_at: datetime | None = Field(None, description='过期时间')
    expired_left: int | None = Field(None, description='剩余过期时间')
    audit_status: int = Field(0, description='审核状态(0待审核 1通过 2拒绝)')
    status: int = Field(1, description='状态(0停用 1正常)')
    file_only_num: str | None = Field(None, description='文件唯一编号')
    file_size: int | None = Field(None, description='文件大小')
    path_info: str | None = Field(None, description='路径信息')
    file_id: str | None = Field(None, description='文件 ID')
    content: str | None = Field(None, description='内容')
    uk_uid: str | None = Field(None, description='用户唯一标识')
    storage_key: str | None = Field(None, description='存储对象 Key')
    file_type: str | None = Field(None, description='文件类型')


class CreateResourceParam(SchemaBase):
    """创建资源参数"""

    category_id: int = Field(description='分类 ID')
    resource_type: str = Field(description='资源类型')
    url: str = Field(description='链接')
    url_type: DriveType = Field(description='链接类型')
    user_id: int = Field(description='所属用户 ID')

    remark: str | None = Field(None, description='资源标题')
    org_name: str | None = Field(None, description='机构或老师名称')
    resource_intro: str | None = Field(None, description='资源介绍')
    resource_image: JsonValue | None = Field(None, description='资源图片 JSON')
    extract_code: str | None = Field(None, description='提取码')
    is_temp_file: int = Field(0, ge=0, le=3, description='临时处理模式(0无操作 1定时删除 2定时刷新 3定时更新)')
    price: Decimal | None = Field(None, description='价格')
    suggested_price: Decimal | None = Field(None, description='建议价格')
    sort: int = Field(0, description='排序')
    storage_key: str | None = Field(None, description='存储对象 Key')
    file_type: str | None = Field(None, description='文件类型')


class UpdateResourceParam(SchemaBase):
    """更新资源参数"""

    category_id: int | None = Field(None, description='分类 ID')
    resource_type: str | None = Field(None, description='资源类型')
    remark: str | None = Field(None, description='资源标题')
    org_name: str | None = Field(None, description='机构或老师名称')
    resource_intro: str | None = Field(None, description='资源介绍')
    resource_image: JsonValue | None = Field(None, description='资源图片 JSON')
    url: str | None = Field(None, description='链接')
    url_type: DriveType | None = Field(None, description='链接类型')
    extract_code: str | None = Field(None, description='提取码')
    is_temp_file: int | None = Field(
        None, ge=0, le=3, description='临时处理模式(0无操作 1定时删除 2定时刷新 3定时更新)'
    )
    price: Decimal | None = Field(None, description='价格')
    suggested_price: Decimal | None = Field(None, description='建议价格')
    sort: int | None = Field(None, description='排序')
    title: str | None = Field(None, description='分享标题')
    share_id: str | None = Field(None, description='分享 ID')
    pwd_id: str | None = Field(None, description='密码 ID')
    expired_type: int | None = Field(None, description='过期类型(0永久 1定时)')
    view_count: int | None = Field(None, description='浏览量')
    expired_at: datetime | None = Field(None, description='过期时间')
    expired_left: int | None = Field(None, description='剩余过期时间')
    audit_status: int | None = Field(None, description='审核状态(0待审核 1通过 2拒绝)')
    status: int | None = Field(None, description='状态(0停用 1正常)')
    file_only_num: str | None = Field(None, description='文件唯一编号')
    file_size: int | None = Field(None, description='文件大小')
    path_info: str | None = Field(None, description='路径信息')
    file_id: str | None = Field(None, description='文件 ID')
    content: str | None = Field(None, description='内容')
    uk_uid: str | None = Field(None, description='用户唯一标识')
    storage_key: str | None = Field(None, description='存储对象 Key')
    file_type: str | None = Field(None, description='文件类型')


class UpdateResourceUserParam(SchemaBase):
    """用户更新资源参数"""

    category_id: int | None = Field(None, description='分类 ID')
    resource_type: str | None = Field(None, description='资源类型')
    remark: str | None = Field(None, description='资源标题')
    org_name: str | None = Field(None, description='机构或老师名称')
    resource_intro: str | None = Field(None, description='资源介绍')
    resource_image: JsonValue | None = Field(None, description='资源图片 JSON')
    url: str | None = Field(None, description='链接')
    url_type: DriveType | None = Field(None, description='链接类型')
    extract_code: str | None = Field(None, description='提取码')
    is_temp_file: int | None = Field(
        None, ge=0, le=3, description='临时处理模式(0无操作 1定时删除 2定时刷新 3定时更新)'
    )
    price: Decimal | None = Field(None, description='价格')
    suggested_price: Decimal | None = Field(None, description='建议价格')
    sort: int | None = Field(None, description='排序')
    storage_key: str | None = Field(None, description='存储对象 Key')
    file_type: str | None = Field(None, description='文件类型')


class BatchDeleteResourceParam(SchemaBase):
    """批量删除资源参数"""

    ids: list[int] = Field(description='资源 ID 列表', min_length=1)


class GetResourceDetail(ResourceBase):
    """资源详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='主键 ID')
    category_id: int | None = Field(None, description='分类 ID')
    category_name: str | None = Field(None, description='分类名称')
    user_id: int = Field(description='所属用户 ID')
    is_deleted: bool = Field(False, description='是否删除')
    created_by: int = Field(description='创建者')
    updated_by: int | None = Field(None, description='修改者')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class GetResourceListParam(SchemaBase):
    """获取资源列表参数"""

    category_id: int | None = Field(None, description='分类 ID')
    resource_type: str | None = Field(None, description='资源类型')
    url_type: DriveType | None = Field(None, description='链接类型')
    status: int | None = Field(None, description='状态')
    expired_type: int | None = Field(None, description='过期类型')
    user_id: int | None = Field(None, description='所属用户 ID')
    is_deleted: bool | None = Field(None, description='是否删除')
    keyword: str | None = Field(None, description='关键词搜索(标题、机构、介绍)')


class ResourceListItem(SchemaBase):
    """资源列表项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='主键 ID')
    category_id: int = Field(description='分类 ID')
    category_name: str | None = Field(None, description='分类名称')
    remark: str | None = Field(None, description='资源标题')
    title: str | None = Field(None, description='分享标题')
    org_name: str | None = Field(None, description='机构或老师名称')
    resource_type: str = Field(description='资源类型')
    resource_intro: str | None = Field(None, description='资源介绍')
    resource_image: JsonValue | None = Field(None, description='资源图片 JSON')
    url_type: DriveType = Field(description='链接类型')
    url: str = Field(description='链接')
    file_size: int | None = Field(None, description='文件大小')
    storage_key: str | None = Field(None, description='存储对象 Key')
    file_type: str | None = Field(None, description='文件类型')
    hot: int = Field(0, description='热度值')
    status: int = Field(1, description='状态(0停用 1正常)')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class ResourceKnowledgeItem(SchemaBase):
    """资源知识库项"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='主键 ID')
    category_id: int = Field(description='分类 ID')
    category_name: str | None = Field(None, description='分类名称')
    remark: str | None = Field(None, description='资源标题')
    title: str | None = Field(None, description='分享标题')
    org_name: str | None = Field(None, description='机构或老师名称')
    resource_type: str = Field(description='资源类型')
    resource_intro: str | None = Field(None, description='资源介绍')
    content: str | None = Field(None, description='完整内容')
    url_type: DriveType = Field(description='链接类型')
    url: str = Field(description='链接')
    extract_code: str | None = Field(None, description='提取码')
    price: Decimal | None = Field(None, description='价格')
    suggested_price: Decimal | None = Field(None, description='建议价格')
    view_count: int = Field(0, description='浏览量')
    created_time: datetime = Field(description='创建时间')
    updated_time: datetime | None = Field(None, description='更新时间')


class VectorSearchResultItem(SchemaBase):
    """向量搜索结果项"""

    resource: ResourceListItem = Field(description='资源信息')
    similarity: float = Field(description='相似度分数 (0-1)')


class VectorSearchKnowledgeResultItem(SchemaBase):
    """向量搜索知识库结果项"""

    resource: ResourceKnowledgeItem = Field(description='资源详细信息')
    similarity: float = Field(description='相似度分数 (0-1)')


class ResourceStatistics(SchemaBase):
    """资源统计"""

    total_count: int = Field(0, description='总数量')
    active_count: int = Field(0, description='正常状态数量')
    pending_audit_count: int = Field(0, description='待审核数量')
    approved_count: int = Field(0, description='已通过审核数量')
    rejected_count: int = Field(0, description='已拒绝数量')
    deleted_count: int = Field(0, description='已删除数量')
    total_views: int = Field(0, description='总浏览量')
    today_start_views: int = Field(0, description='今日 0 点总浏览量')
    today_growth: int = Field(0, description='今日增长量')


class ResourceViewHistoryBase(SchemaBase):
    """浏览量历史记录基础 schema"""

    pwd_id: str = Field(description='资源唯一 ID')
    view_count: int = Field(0, description='当时的浏览量')


class CreateResourceViewHistoryParam(ResourceViewHistoryBase):
    """创建浏览量历史记录参数"""

    pass


class GetResourceViewHistoryDetail(ResourceViewHistoryBase):
    """获取浏览量历史记录详情"""

    id: int = Field(description='记录 ID')
    record_time: datetime = Field(description='记录时间')


class GetResourceViewHistoryListParam(SchemaBase):
    """获取浏览量历史记录列表参数"""

    pwd_id: str | None = Field(None, description='资源唯一 ID')
    start_time: datetime | None = Field(None, description='开始时间')
    end_time: datetime | None = Field(None, description='结束时间')


class ResourceViewTrendData(SchemaBase):
    """资源浏览量趋势数据"""

    record_time: datetime = Field(description='记录时间')
    view_count: int = Field(0, description='浏览量')


class GetResourceViewTrendParam(SchemaBase):
    """获取资源浏览量趋势参数"""

    pwd_id: str = Field(description='资源唯一 ID')
    start_time: datetime | None = Field(None, description='开始时间')
    end_time: datetime | None = Field(None, description='结束时间')


class ResourceViewTrendResponse(SchemaBase):
    """资源浏览量趋势响应"""

    pwd_id: str = Field(description='资源唯一 ID')
    current_view_count: int = Field(0, description='当前浏览量')
    trend_data: list[ResourceViewTrendData] = Field(default_factory=list, description='趋势数据')


class UpdateResourceViewCountParam(SchemaBase):
    """更新资源浏览量参数"""

    pwd_id: str = Field(description='资源唯一 ID')
    view_count: int = Field(description='新的浏览量')


class OverallStatisticsTrendData(SchemaBase):
    """整体统计趋势数据点"""

    date: str = Field(description='日期 (YYYY-MM-DD)')
    total_count: int = Field(0, description='总资源数')
    total_views: int = Field(0, description='总浏览量')
    active_count: int = Field(0, description='活跃资源数')
    new_resources: int = Field(0, description='新增资源数')


class GetOverallStatisticsTrendParam(SchemaBase):
    """获取整体统计趋势参数"""

    start_date: str | None = Field(None, description='开始日期 (YYYY-MM-DD)')
    end_date: str | None = Field(None, description='结束日期 (YYYY-MM-DD)')
    days: int | None = Field(7, description='获取最近天数 (默认 7)')


class OverallStatisticsTrendResponse(SchemaBase):
    """整体统计趋势响应"""

    trend_data: list[OverallStatisticsTrendData] = Field(default_factory=list, description='趋势数据')
    summary: dict = Field(default_factory=dict, description='汇总信息')


class GongkaoResourceResponse(SchemaBase):
    """公考网站专用资源返回详情"""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(description='主键 ID')
    title: str | None = Field(None, description='标题')
    remark: str | None = Field(None, description='资源标题')
    org_name: str | None = Field(None, description='机构或老师名称')
    url_type: DriveType = Field(description='链接类型')
    url: str = Field(description='链接')
    storage_key: str | None = Field(None, description='存储对象 Key')
    file_type: str | None = Field(None, description='文件类型')
    hot: int = Field(0, description='热度值')
    category_id: int = Field(description='分类 ID')
    file_size: int | None = Field(None, description='文件大小')
    created_time: datetime = Field(description='创建时间')
