#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Path, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.coulddrive.schema.rule_template import (
    CreateRuleTemplateParam,
    UpdateRuleTemplateParam,
    GetRuleTemplateDetail,
    GetRuleTemplateListParam,
    RuleTemplateListItem,
    UseRuleTemplateParam,
    BatchDeleteRuleTemplateParam,
    RuleTemplateStatsDetail,
    TemplateType
)
from backend.app.coulddrive.service.rule_template_service import rule_template_service
from backend.common.pagination import DependsPagination, PageData, paging_data, _CustomPageParams
from backend.common.response.response_schema import ResponseModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter()


@router.get("/list", summary="获取规则模板列表", dependencies=[DependsJwtAuth, DependsPagination])
async def get_rule_template_list(
    db: CurrentSession,
    page_params: Annotated[_CustomPageParams, DependsPagination],
    template_type: Annotated[TemplateType | None, Query(description="模板类型")] = None,
    category: Annotated[str | None, Query(description="分类")] = None,
    is_active: Annotated[bool | None, Query(description="是否启用")] = None,
    is_system: Annotated[bool | None, Query(description="是否系统内置模板")] = None,
    keyword: Annotated[str | None, Query(description="关键词搜索")] = None,
) -> ResponseModel:
    """获取规则模板列表"""
    params = GetRuleTemplateListParam(
        template_type=template_type,
        category=category,
        is_active=is_active,
        is_system=is_system,
        keyword=keyword
    )
    
    rule_templates = await rule_template_service.get_rule_template_list(db, params)
    
    # 转换为列表项格式
    template_list = [RuleTemplateListItem.model_validate(template) for template in rule_templates]
    
    # 这里需要使用正确的分页函数，但先简化返回
    return response_base.success(data=template_list)


@router.get("/{template_id}", summary="获取规则模板详情", dependencies=[DependsJwtAuth])
async def get_rule_template_detail(
    db: CurrentSession,
    template_id: Annotated[int, Path(description="模板ID")]
) -> ResponseModel:
    """获取规则模板详情"""
    rule_template = await rule_template_service.get_rule_template(db, template_id)
    template_detail = GetRuleTemplateDetail.model_validate(rule_template)
    return response_base.success(data=template_detail)


@router.post("/", summary="创建规则模板", dependencies=[DependsJwtAuth])
async def create_rule_template(
    db: CurrentSession,
    obj: CreateRuleTemplateParam,
    request: Request
) -> ResponseModel:
    """创建规则模板"""
    await rule_template_service.create_rule_template(db, obj, request.user.id)
    return response_base.success()


@router.put("/{template_id}", summary="更新规则模板", dependencies=[DependsJwtAuth])
async def update_rule_template(
    db: CurrentSession,
    template_id: Annotated[int, Path(description="模板ID")],
    obj: UpdateRuleTemplateParam,
    request: Request
) -> ResponseModel:
    """更新规则模板"""
    await rule_template_service.update_rule_template(db, template_id, obj, request.user.id)
    return response_base.success()


@router.delete("/", summary="批量删除规则模板", dependencies=[DependsJwtAuth])
async def delete_rule_templates(
    db: CurrentSession,
    obj: BatchDeleteRuleTemplateParam
) -> ResponseModel:
    """批量删除规则模板"""
    await rule_template_service.delete_rule_templates(db, obj.ids)
    return response_base.success()


@router.post("/{template_id}/use", summary="使用规则模板", dependencies=[DependsJwtAuth])
async def use_rule_template(
    db: CurrentSession,
    template_id: Annotated[int, Path(description="模板ID")]
) -> ResponseModel:
    """使用规则模板（更新使用统计并返回模板配置）"""
    rule_template = await rule_template_service.use_rule_template(db, template_id)
    template_detail = GetRuleTemplateDetail.model_validate(rule_template)
    return response_base.success(data=template_detail)


@router.patch("/{template_id}/toggle", summary="切换规则模板启用状态", dependencies=[DependsJwtAuth])
async def toggle_rule_template_active(
    db: CurrentSession,
    template_id: Annotated[int, Path(description="模板ID")],
    is_active: Annotated[bool, Query(description="是否启用")]
) -> ResponseModel:
    """切换规则模板启用状态"""
    await rule_template_service.toggle_rule_template_active(db, template_id, is_active)
    return response_base.success()


@router.get("/stats/overview", summary="获取规则模板统计信息", dependencies=[DependsJwtAuth])
async def get_rule_template_stats(db: CurrentSession) -> ResponseModel:
    """获取规则模板统计信息"""
    stats = await rule_template_service.get_rule_template_stats(db)
    return response_base.success(data=stats)


@router.get("/type/{template_type}", summary="根据类型获取规则模板", dependencies=[DependsJwtAuth])
async def get_templates_by_type(
    db: CurrentSession,
    template_type: Annotated[TemplateType, Path(description="模板类型")]
) -> ResponseModel:
    """根据类型获取规则模板"""
    rule_templates = await rule_template_service.get_templates_by_type(db, template_type)
    template_list = [RuleTemplateListItem.model_validate(template) for template in rule_templates]
    return response_base.success(data=template_list)


@router.get("/category/{category}", summary="根据分类获取规则模板", dependencies=[DependsJwtAuth])
async def get_templates_by_category(
    db: CurrentSession,
    category: Annotated[str, Path(description="分类")]
) -> ResponseModel:
    """根据分类获取规则模板"""
    rule_templates = await rule_template_service.get_templates_by_category(db, category)
    template_list = [RuleTemplateListItem.model_validate(template) for template in rule_templates]
    return response_base.success(data=template_list) 