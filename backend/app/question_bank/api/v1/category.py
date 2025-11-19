#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.app.question_bank.schema.category import (
    CreateCategoryParam,
    DeleteCategoryParam,
    GetCategoryDetail,
    GetCategoryTree,
    UpdateCategoryParam,
)
from backend.app.question_bank.service.category_service import category_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='获取分类详情', name='qbank_get_category')
async def get_category(
    db: CurrentSession, pk: Annotated[int, Path(description='分类 ID')]
) -> ResponseSchemaModel[GetCategoryDetail]:
    """🌍 公开接口 - 任何人都可以查看分类详情"""
    data = await category_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('', summary='获取分类树', name='qbank_get_category_tree')
async def get_category_tree(
    db: CurrentSession,
    cat_type: Annotated[int | None, Query(description='分类类型')] = None,
    is_active: Annotated[bool | None, Query(description='是否启用')] = None,
) -> ResponseSchemaModel[list[GetCategoryTree]]:
    """🌍 公开接口 - 任何人都可以查看分类树"""
    tree = await category_service.get_tree(db=db, cat_type=cat_type, is_active=is_active)
    return response_base.success(data=tree)


@router.post(
    '',
    summary='创建分类',
    name='qbank_create_category',
    dependencies=[
        Depends(RequestPermission('question_bank:category:create')),
        DependsRBAC,
    ],
)
async def create_category(db: CurrentSessionTransaction, obj: CreateCategoryParam) -> ResponseModel:
    """🔐 管理员接口 - 只有管理员可以创建分类"""
    await category_service.create(db=db, obj=obj)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新分类',
    name='qbank_update_category',
    dependencies=[
        Depends(RequestPermission('question_bank:category:update')),
        DependsRBAC,
    ],
)
async def update_category(
    db: CurrentSessionTransaction, pk: Annotated[int, Path(description='分类 ID')], obj: UpdateCategoryParam
) -> ResponseModel:
    """🔐 管理员接口 - 只有管理员可以更新分类"""
    count = await category_service.update(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '',
    summary='删除分类',
    name='qbank_delete_category',
    dependencies=[
        Depends(RequestPermission('question_bank:category:delete')),
        DependsRBAC,
    ],
)
async def delete_category(db: CurrentSessionTransaction, obj: DeleteCategoryParam) -> ResponseModel:
    """🔐 管理员接口 - 只有管理员可以删除分类"""
    count = await category_service.delete(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()
