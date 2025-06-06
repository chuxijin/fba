#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import Any
from enum import Enum

from pydantic import ConfigDict, Field, field_validator

from backend.common.schema import SchemaBase


class TemplateType(str, Enum):
    """模板类型枚举"""
    EXCLUSION = "exclusion"
    RENAME = "rename"
    CUSTOM = "custom"


class RuleTemplateBase(SchemaBase):
    """规则模板基础"""
    
    template_name: str = Field(..., description="模板名称")
    template_type: TemplateType = Field(..., description="模板类型")
    description: str | None = Field(None, description="模板描述")
    rule_config: dict[str, Any] = Field(..., description="规则配置")
    category: str | None = Field(None, description="分类")
    tags: list[str] | None = Field(None, description="标签")

    @field_validator('template_name')
    @classmethod
    def validate_template_name(cls, v: str) -> str:
        """验证模板名称"""
        if not v or not v.strip():
            raise ValueError("模板名称不能为空")
        if len(v.strip()) > 100:
            raise ValueError("模板名称长度不能超过100个字符")
        return v.strip()

    @field_validator('rule_config')
    @classmethod
    def validate_rule_config(cls, v: dict[str, Any]) -> dict[str, Any]:
        """验证规则配置"""
        if not v:
            raise ValueError("规则配置不能为空")
        return v


class CreateRuleTemplateParam(RuleTemplateBase):
    """创建规则模板参数"""
    pass


class UpdateRuleTemplateParam(SchemaBase):
    """更新规则模板参数"""
    
    template_name: str | None = Field(None, description="模板名称")
    template_type: TemplateType | None = Field(None, description="模板类型")
    description: str | None = Field(None, description="模板描述")
    rule_config: dict[str, Any] | None = Field(None, description="规则配置")
    category: str | None = Field(None, description="分类")
    tags: list[str] | None = Field(None, description="标签")
    is_active: bool | None = Field(None, description="是否启用")

    @field_validator('template_name')
    @classmethod
    def validate_template_name(cls, v: str | None) -> str | None:
        """验证模板名称"""
        if v is not None:
            if not v or not v.strip():
                raise ValueError("模板名称不能为空")
            if len(v.strip()) > 100:
                raise ValueError("模板名称长度不能超过100个字符")
            return v.strip()
        return v

    @field_validator('rule_config')
    @classmethod
    def validate_rule_config(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        """验证规则配置"""
        if v is not None and not v:
            raise ValueError("规则配置不能为空")
        return v


class GetRuleTemplateDetail(RuleTemplateBase):
    """规则模板详情"""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int = Field(..., description="主键ID")
    is_active: bool = Field(..., description="是否启用")
    is_system: bool = Field(..., description="是否系统内置模板")
    usage_count: int = Field(..., description="使用次数")
    last_used_at: datetime | None = Field(None, description="最后使用时间")
    created_by: int = Field(..., description="创建者")
    updated_by: int = Field(..., description="更新者")
    created_time: datetime = Field(..., description="创建时间")
    updated_time: datetime = Field(..., description="更新时间")


class GetRuleTemplateListParam(SchemaBase):
    """获取规则模板列表参数"""
    
    template_type: TemplateType | None = Field(None, description="模板类型")
    category: str | None = Field(None, description="分类")
    is_active: bool | None = Field(None, description="是否启用")
    is_system: bool | None = Field(None, description="是否系统内置模板")
    keyword: str | None = Field(None, description="关键词搜索（模板名称或描述）")


class RuleTemplateListItem(SchemaBase):
    """规则模板列表项"""
    
    model_config = ConfigDict(from_attributes=True)
    
    id: int = Field(..., description="主键ID")
    template_name: str = Field(..., description="模板名称")
    template_type: TemplateType = Field(..., description="模板类型")
    description: str | None = Field(None, description="模板描述")
    category: str | None = Field(None, description="分类")
    tags: list[str] | None = Field(None, description="标签")
    is_active: bool = Field(..., description="是否启用")
    is_system: bool = Field(..., description="是否系统内置模板")
    usage_count: int = Field(..., description="使用次数")
    last_used_at: datetime | None = Field(None, description="最后使用时间")
    created_time: datetime = Field(..., description="创建时间")


class UseRuleTemplateParam(SchemaBase):
    """使用规则模板参数"""
    
    template_id: int = Field(..., description="模板ID")


class BatchDeleteRuleTemplateParam(SchemaBase):
    """批量删除规则模板参数"""
    
    ids: list[int] = Field(..., description="模板ID列表")

    @field_validator('ids')
    @classmethod
    def validate_ids(cls, v: list[int]) -> list[int]:
        """验证ID列表"""
        if not v:
            raise ValueError("ID列表不能为空")
        if len(v) > 100:
            raise ValueError("单次删除数量不能超过100个")
        return v


class RuleTemplateStatsDetail(SchemaBase):
    """规则模板统计详情"""
    
    total_count: int = Field(..., description="总数量")
    active_count: int = Field(..., description="启用数量")
    system_count: int = Field(..., description="系统模板数量")
    user_count: int = Field(..., description="用户模板数量")
    category_stats: dict[str, int] = Field(..., description="分类统计")
    type_stats: dict[str, int] = Field(..., description="类型统计") 