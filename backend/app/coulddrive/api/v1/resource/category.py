#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Request

from backend.app.coulddrive.schema.category import (
    CreateCategoryParam,
    UpdateCategoryParam,
    GetCategoryDetail,
    GetCategoryListParam,
    CategoryTreeNode,
    CategoryOption,
    GetCategoryOptionsParam,
    CategoryStatistics
)
from backend.app.coulddrive.service.category_service import category_service
from backend.common.pagination import DependsPagination
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter()

@router.get('', summary='获取分类列表', dependencies=[DependsPagination])
async def get_category_list(
    db: CurrentSession,
    params: Annotated[GetCategoryListParam, Depends()]
) -> ResponseModel:
    """获取分类列表"""
    data = await category_service.get_list(db, params)
    return response_base.success(data=data)


@router.get('/tree', summary='获取分类树', dependencies=[DependsJwtAuth])
async def get_category_tree(
    db: CurrentSession,
    category_type: str = None,
    status: int = None
) -> ResponseSchemaModel[list[CategoryTreeNode]]:
    """获取分类树"""
    data = await category_service.get_tree(db, category_type, status)
    return response_base.success(data=data)


@router.get('/options', summary='获取分类选项', dependencies=[DependsJwtAuth])
async def get_category_options(
    db: CurrentSession,
    params: Annotated[GetCategoryOptionsParam, Depends()]
) -> ResponseSchemaModel[list[CategoryOption]]:
    """获取分类选项"""
    data = await category_service.get_options(db, params)
    return response_base.success(data=data)


@router.get('/statistics', summary='获取分类统计', dependencies=[DependsJwtAuth])
async def get_category_statistics(db: CurrentSession) -> ResponseSchemaModel[CategoryStatistics]:
    """获取分类统计"""
    data = await category_service.get_statistics(db)
    return response_base.success(data=data)


@router.get('/domain-subject-mapping', summary='获取领域科目映射', dependencies=[DependsJwtAuth])
async def get_domain_subject_mapping(db: CurrentSession) -> ResponseSchemaModel[dict]:
    """获取领域科目映射"""
    data = await category_service.get_domain_subject_mapping(db)
    return response_base.success(data=data)


@router.post('', summary='创建分类', dependencies=[DependsJwtAuth])
async def create_category(
    request: Request,
    db: CurrentSession,
    params: CreateCategoryParam
) -> ResponseSchemaModel[GetCategoryDetail]:
    """创建分类"""
    data = await category_service.create(db, params, request.user.id)
    return response_base.success(data=data)


@router.get('/{category_id}', summary='获取分类详情', dependencies=[DependsJwtAuth])
async def get_category_detail(
    db: CurrentSession,
    category_id: Annotated[int, Path(description='分类ID')]
) -> ResponseSchemaModel[GetCategoryDetail]:
    """获取分类详情"""
    data = await category_service.get(db, category_id)
    return response_base.success(data=data)


@router.put('/{category_id}', summary='更新分类', dependencies=[DependsJwtAuth])
async def update_category(
    request: Request,
    db: CurrentSession,
    category_id: Annotated[int, Path(description='分类ID')],
    params: UpdateCategoryParam
) -> ResponseSchemaModel[GetCategoryDetail]:
    """更新分类"""
    data = await category_service.update(db, category_id, params, request.user.id)
    return response_base.success(data=data)


@router.delete('/{category_id}', summary='删除分类', dependencies=[DependsJwtAuth])
async def delete_category(
    db: CurrentSession,
    category_id: Annotated[int, Path(description='分类ID')]
) -> ResponseModel:
    """删除分类"""
    await category_service.delete(db, category_id)
    return response_base.success()


@router.get('/name-by-code/{code}', summary='通过编码获取分类名称', dependencies=[DependsJwtAuth])
async def get_category_name_by_code(
    db: CurrentSession,
    code: Annotated[str, Path(description='分类编码')]
) -> ResponseSchemaModel[str]:
    """通过编码获取分类名称"""
    category = await category_service.get_by_code(db, code)
    return response_base.success(data=category.name) 