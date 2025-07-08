#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Optional, List

from pydantic import ConfigDict, Field

from backend.common.schema import SchemaBase


class CategoryBase(SchemaBase):
    """分类基础 schema"""
    
    name: str = Field(..., description="分类名称")
    code: str = Field(..., description="分类编码")
    description: Optional[str] = Field(None, description="分类描述")
    category_type: str = Field(..., description="分类类型(domain-领域, subject-科目, resource_type-资源类型)")
    parent_id: Optional[int] = Field(None, description="父级分类ID")
    level: int = Field(1, description="分类层级")
    path: str = Field(..., description="分类路径")
    sort: int = Field(0, description="排序值")
    status: int = Field(1, description="状态(0停用 1正常)")
    is_system: bool = Field(False, description="是否系统分类")


class CreateCategoryParam(SchemaBase):
    """创建分类参数"""
    
    name: str = Field(..., description="分类名称")
    code: str = Field(..., description="分类编码")
    description: Optional[str] = Field(None, description="分类描述")
    category_type: str = Field(..., description="分类类型(domain-领域, subject-科目, resource_type-资源类型)")
    parent_id: Optional[int] = Field(None, description="父级分类ID")
    sort: int = Field(0, description="排序值")
    status: int = Field(1, description="状态(0停用 1正常)")
    is_system: bool = Field(False, description="是否系统分类")


class UpdateCategoryParam(SchemaBase):
    """更新分类参数"""
    
    name: Optional[str] = Field(None, description="分类名称")
    code: Optional[str] = Field(None, description="分类编码")
    description: Optional[str] = Field(None, description="分类描述")
    category_type: Optional[str] = Field(None, description="分类类型")
    parent_id: Optional[int] = Field(None, description="父级分类ID")
    sort: Optional[int] = Field(None, description="排序值")
    status: Optional[int] = Field(None, description="状态")
    is_system: Optional[bool] = Field(None, description="是否系统分类")


class GetCategoryDetail(CategoryBase):
    """分类详情"""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int = Field(..., description="分类ID")
    created_by: int = Field(..., description="创建者")
    updated_by: Optional[int] = Field(None, description="修改者")
    created_time: datetime = Field(..., description="创建时间")
    updated_time: Optional[datetime] = Field(None, description="更新时间")


class GetCategoryListParam(SchemaBase):
    """获取分类列表参数"""
    
    category_type: Optional[str] = Field(None, description="分类类型")
    parent_id: Optional[int] = Field(None, description="父级分类ID")
    level: Optional[int] = Field(None, description="分类层级")
    status: Optional[int] = Field(None, description="状态")
    keyword: Optional[str] = Field(None, description="关键词搜索(名称、编码)")


class CategoryListItem(SchemaBase):
    """分类列表项"""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int = Field(..., description="分类ID")
    name: str = Field(..., description="分类名称")
    code: str = Field(..., description="分类编码")
    description: Optional[str] = Field(None, description="分类描述")
    category_type: str = Field(..., description="分类类型")
    parent_id: Optional[int] = Field(None, description="父级分类ID")
    level: int = Field(..., description="分类层级")
    path: str = Field(..., description="分类路径")
    sort: int = Field(..., description="排序值")
    status: int = Field(..., description="状态")
    is_system: bool = Field(..., description="是否系统分类")
    created_time: datetime = Field(..., description="创建时间")
    updated_time: Optional[datetime] = Field(None, description="更新时间")


class CategoryTreeNode(SchemaBase):
    """分类树节点"""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int = Field(..., description="分类ID")
    name: str = Field(..., description="分类名称")
    code: str = Field(..., description="分类编码")
    description: Optional[str] = Field(None, description="分类描述")
    category_type: str = Field(..., description="分类类型")
    parent_id: Optional[int] = Field(None, description="父级分类ID")
    level: int = Field(..., description="分类层级")
    path: str = Field(..., description="分类路径")
    sort: int = Field(..., description="排序值")
    status: int = Field(..., description="状态")
    is_system: bool = Field(..., description="是否系统分类")
    children: List["CategoryTreeNode"] = Field([], description="子分类")


class GetCategoryTreeParam(SchemaBase):
    """获取分类树参数"""
    
    category_type: Optional[str] = Field(None, description="分类类型")
    status: Optional[int] = Field(None, description="状态")
    max_level: Optional[int] = Field(None, description="最大层级")


class CategoryOption(SchemaBase):
    """分类选项"""
    
    label: str = Field(..., description="显示名称")
    value: str = Field(..., description="选项值")
    category_type: str = Field(..., description="分类类型")
    level: int = Field(..., description="层级")
    disabled: bool = Field(False, description="是否禁用")


class GetCategoryOptionsParam(SchemaBase):
    """获取分类选项参数"""
    
    category_type: Optional[str] = Field(None, description="分类类型")
    parent_id: Optional[int] = Field(None, description="父级分类ID")
    status: Optional[int] = Field(1, description="状态")


# 批量操作相关 Schema
class BatchUpdateCategoryStatusParam(SchemaBase):
    """批量更新分类状态参数"""
    
    category_ids: List[int] = Field(..., description="分类ID列表")
    status: int = Field(..., description="状态")


class BatchDeleteCategoryParam(SchemaBase):
    """批量删除分类参数"""
    
    category_ids: List[int] = Field(..., description="分类ID列表")
    force_delete: bool = Field(False, description="是否强制删除(忽略系统分类限制)")


class MoveCategoryParam(SchemaBase):
    """移动分类参数"""
    
    category_id: int = Field(..., description="分类ID")
    target_parent_id: Optional[int] = Field(None, description="目标父级ID")
    target_position: Optional[int] = Field(None, description="目标位置")


# 统计相关 Schema
class CategoryStatistics(SchemaBase):
    """分类统计"""
    
    total_count: int = Field(0, description="总数量")
    active_count: int = Field(0, description="正常状态数量")
    inactive_count: int = Field(0, description="停用状态数量")
    system_count: int = Field(0, description="系统分类数量")
    by_type: dict = Field({}, description="按类型统计")
    by_level: dict = Field({}, description="按层级统计") 