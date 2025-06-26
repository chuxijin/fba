#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase
from backend.app.coulddrive.schema.file import BaseShareInfo
from backend.app.coulddrive.schema.enum import DriveType


class ResourceBase(SchemaBase):
    """资源基础 schema"""
    
    # 用户手动填写的必填字段
    domain: str = Field(..., description="领域")
    subject: str = Field(..., description="科目")
    main_name: str = Field(..., description="主要名字")
    resource_type: str = Field(..., description="资源类型")
    url: str = Field(..., description="链接")
    url_type: DriveType = Field(..., description="链接类型")
    
    # 用户手动填写的可选字段
    description: Optional[str] = Field(None, description="描述")
    resource_intro: Optional[str] = Field(None, description="资源介绍")
    resource_image: Optional[str] = Field(None, description="资源图片")
    extract_code: Optional[str] = Field(None, description="提取码")
    is_temp_file: bool = Field(False, description="是否为临时文件")
    price: Optional[Decimal] = Field(None, description="价格")
    suggested_price: Optional[Decimal] = Field(None, description="建议价格")
    sort: int = Field(0, description="排序")
    remark: Optional[str] = Field(None, description="备注")
    
    # 自动获取的字段（可选，通常由系统自动填充）
    title: Optional[str] = Field(None, description="分享标题")
    share_id: Optional[str] = Field(None, description="分享ID")
    pwd_id: Optional[str] = Field(None, description="密码ID")
    expired_type: int = Field(0, description="过期类型(0永久 1定时)")
    view_count: int = Field(0, description="浏览量")
    expired_at: Optional[datetime] = Field(None, description="过期时间")
    expired_left: Optional[int] = Field(None, description="剩余过期时间")
    audit_status: int = Field(0, description="审核状态(0待审核 1通过 2拒绝)")
    status: int = Field(1, description="状态(0停用 1正常)")
    file_only_num: Optional[str] = Field(None, description="文件唯一编号")
    file_size: Optional[int] = Field(None, description="文件大小")
    path_info: Optional[str] = Field(None, description="路径信息")
    file_id: Optional[str] = Field(None, description="文件ID")
    content: Optional[str] = Field(None, description="内容")
    uk_uid: Optional[str] = Field(None, description="用户唯一标识")


class CreateResourceParam(SchemaBase):
    """创建资源参数"""
    
    # 用户手动填写的必填字段
    domain: str = Field(..., description="领域")
    subject: str = Field(..., description="科目")
    main_name: str = Field(..., description="主要名字")
    resource_type: str = Field(..., description="资源类型")
    url: str = Field(..., description="链接")
    url_type: DriveType = Field(..., description="链接类型")
    user_id: int = Field(..., description="所属用户ID")
    
    # 用户手动填写的可选字段
    description: Optional[str] = Field(None, description="描述")
    resource_intro: Optional[str] = Field(None, description="资源介绍")
    resource_image: Optional[str] = Field(None, description="资源图片")
    extract_code: Optional[str] = Field(None, description="提取码")
    is_temp_file: bool = Field(False, description="是否为临时文件")
    price: Optional[Decimal] = Field(None, description="价格")
    suggested_price: Optional[Decimal] = Field(None, description="建议价格")
    sort: int = Field(0, description="排序")
    remark: Optional[str] = Field(None, description="备注")


class UpdateResourceParam(SchemaBase):
    """更新资源参数"""
    
    # 所有字段都是可选的
    domain: Optional[str] = Field(None, description="领域")
    subject: Optional[str] = Field(None, description="科目")
    main_name: Optional[str] = Field(None, description="主要名字")
    resource_type: Optional[str] = Field(None, description="资源类型")
    description: Optional[str] = Field(None, description="描述")
    resource_intro: Optional[str] = Field(None, description="资源介绍")
    resource_image: Optional[str] = Field(None, description="资源图片")
    url: Optional[str] = Field(None, description="链接")
    url_type: Optional[DriveType] = Field(None, description="链接类型")
    extract_code: Optional[str] = Field(None, description="提取码")
    is_temp_file: Optional[bool] = Field(None, description="是否为临时文件")
    price: Optional[Decimal] = Field(None, description="价格")
    suggested_price: Optional[Decimal] = Field(None, description="建议价格")
    sort: Optional[int] = Field(None, description="排序")
    remark: Optional[str] = Field(None, description="备注")
    title: Optional[str] = Field(None, description="分享标题")
    share_id: Optional[str] = Field(None, description="分享ID")
    pwd_id: Optional[str] = Field(None, description="密码ID")
    expired_type: Optional[int] = Field(None, description="过期类型(0永久 1定时)")
    view_count: Optional[int] = Field(None, description="浏览量")
    expired_at: Optional[datetime] = Field(None, description="过期时间")
    expired_left: Optional[int] = Field(None, description="剩余过期时间")
    audit_status: Optional[int] = Field(None, description="审核状态(0待审核 1通过 2拒绝)")
    status: Optional[int] = Field(None, description="状态(0停用 1正常)")
    file_only_num: Optional[str] = Field(None, description="文件唯一编号")
    file_size: Optional[int] = Field(None, description="文件大小")
    path_info: Optional[str] = Field(None, description="路径信息")
    file_id: Optional[str] = Field(None, description="文件ID")
    content: Optional[str] = Field(None, description="内容")
    uk_uid: Optional[str] = Field(None, description="用户唯一标识")


class UpdateResourceUserParam(SchemaBase):
    """用户更新资源参数（Swagger 显示用）"""
    
    # 用户可以修改的基本信息字段
    domain: Optional[str] = Field(None, description="领域")
    subject: Optional[str] = Field(None, description="科目")
    main_name: Optional[str] = Field(None, description="主要名字")
    resource_type: Optional[str] = Field(None, description="资源类型")
    description: Optional[str] = Field(None, description="描述")
    resource_intro: Optional[str] = Field(None, description="资源介绍")
    resource_image: Optional[str] = Field(None, description="资源图片")
    url: Optional[str] = Field(None, description="链接")
    url_type: Optional[DriveType] = Field(None, description="链接类型")
    extract_code: Optional[str] = Field(None, description="提取码")
    is_temp_file: Optional[bool] = Field(None, description="是否为临时文件")
    price: Optional[Decimal] = Field(None, description="价格")
    suggested_price: Optional[Decimal] = Field(None, description="建议价格")
    sort: Optional[int] = Field(None, description="排序")
    remark: Optional[str] = Field(None, description="备注")


class GetResourceDetail(ResourceBase):
    """资源详情"""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int = Field(..., description="主键ID")
    user_id: int = Field(..., description="所属用户ID")
    is_deleted: bool = Field(False, description="是否删除")
    created_by: int = Field(..., description="创建者")
    updated_by: Optional[int] = Field(None, description="修改者")
    created_time: datetime = Field(..., description="创建时间")
    updated_time: Optional[datetime] = Field(None, description="更新时间")


class GetResourceListParam(SchemaBase):
    """获取资源列表参数"""
    
    domain: Optional[str] = Field(None, description="领域")
    subject: Optional[str] = Field(None, description="科目")
    resource_type: Optional[str] = Field(None, description="资源类型")
    url_type: Optional[DriveType] = Field(None, description="链接类型")
    status: Optional[int] = Field(None, description="状态")
    audit_status: Optional[int] = Field(None, description="审核状态")
    user_id: Optional[int] = Field(None, description="所属用户ID")
    is_deleted: Optional[bool] = Field(None, description="是否删除")
    keyword: Optional[str] = Field(None, description="关键词搜索(标题、主要名字)")


class ResourceListItem(SchemaBase):
    """资源列表项"""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int = Field(..., description="主键ID")
    domain: str = Field(..., description="领域")
    subject: str = Field(..., description="科目")
    main_name: str = Field(..., description="主要名字")
    title: Optional[str] = Field(None, description="标题")
    resource_type: str = Field(..., description="资源类型")
    url_type: DriveType = Field(..., description="链接类型")
    url: str = Field(..., description="链接")
    price: Optional[Decimal] = Field(None, description="价格")
    suggested_price: Optional[Decimal] = Field(None, description="建议价格")
    view_count: int = Field(0, description="浏览量")
    sort: int = Field(0, description="排序")
    status: int = Field(1, description="状态(0停用 1正常)")
    audit_status: int = Field(0, description="审核状态(0待审核 1通过 2拒绝)")
    is_deleted: bool = Field(False, description="是否删除")
    user_id: int = Field(..., description="所属用户ID")
    remark: Optional[str] = Field(None, description="备注")
    created_time: datetime = Field(..., description="创建时间")
    updated_time: Optional[datetime] = Field(None, description="更新时间")


class ResourceStatistics(SchemaBase):
    """资源统计"""
    
    total_count: int = Field(0, description="总数量")
    active_count: int = Field(0, description="正常状态数量")
    pending_audit_count: int = Field(0, description="待审核数量")
    approved_count: int = Field(0, description="已通过审核数量")
    rejected_count: int = Field(0, description="已拒绝数量")
    deleted_count: int = Field(0, description="已删除数量")
    total_views: int = Field(0, description="总浏览量")
    today_start_views: int = Field(0, description="今日0点总浏览量")
    today_growth: int = Field(0, description="今日增长量")


# 浏览量历史记录相关Schema
class ResourceViewHistoryBase(SchemaBase):
    """浏览量历史记录基础schema"""
    pwd_id: str = Field(..., description="资源唯一ID")
    view_count: int = Field(0, description="当时的浏览量")


class CreateResourceViewHistoryParam(ResourceViewHistoryBase):
    """创建浏览量历史记录参数"""
    pass


class GetResourceViewHistoryDetail(ResourceViewHistoryBase):
    """获取浏览量历史记录详情"""
    id: int = Field(..., description="记录ID")
    record_time: datetime = Field(..., description="记录时间")


class GetResourceViewHistoryListParam(SchemaBase):
    """获取浏览量历史记录列表参数"""
    pwd_id: Optional[str] = Field(None, description="资源唯一ID")
    start_time: Optional[datetime] = Field(None, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")


class ResourceViewTrendData(SchemaBase):
    """资源浏览量趋势数据"""
    record_time: datetime = Field(..., description="记录时间")
    view_count: int = Field(0, description="浏览量")


class GetResourceViewTrendParam(SchemaBase):
    """获取资源浏览量趋势参数"""
    pwd_id: str = Field(..., description="资源唯一ID")
    start_time: Optional[datetime] = Field(None, description="开始时间")
    end_time: Optional[datetime] = Field(None, description="结束时间")


class ResourceViewTrendResponse(SchemaBase):
    """资源浏览量趋势响应"""
    pwd_id: str = Field(..., description="资源唯一ID")
    current_view_count: int = Field(0, description="当前浏览量")
    trend_data: List[ResourceViewTrendData] = Field([], description="趋势数据")


class UpdateResourceViewCountParam(SchemaBase):
    """更新资源浏览量参数"""
    pwd_id: str = Field(..., description="资源唯一ID")
    view_count: int = Field(..., description="新的浏览量") 