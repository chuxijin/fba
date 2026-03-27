#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.app.gongkao.schema.category import (
    CategoryParam,
    CreateCategoryParam,
    DeleteCategoryParam,
    GetCategoryDetail,
    UpdateCategoryParam,
)
from backend.app.gongkao.service.category_service import category_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get(
    '/tree',
    summary='获取分类树',
    dependencies=[DependsJwtAuth],
)
async def get_gongkao_category_tree(
    db: CurrentSession,
    name: Annotated[str | None, Query(description='分类名称')] = None,
    category_type: Annotated[str | None, Query(description='分类类型', alias='type')] = None,
    parent_id: Annotated[int | None, Query(description='父级分类 ID')] = None,
    status: Annotated[bool | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[list]:
    """获取分类树"""
    params = CategoryParam(
        name=name,
        type=category_type,
        parent_id=parent_id,
        status=status,
    )
    data = await category_service.get_tree(db=db, params=params)
    return response_base.success(data=data)


@router.get('/{pk}', summary='获取分类详情')
async def get_gongkao_category(
    db: CurrentSession,
    pk: Annotated[int, Path(description='分类 ID')],
) -> ResponseSchemaModel[GetCategoryDetail]:
    """获取分类详情"""
    data = await category_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get(
    '',
    summary='获取分类列表',
    dependencies=[DependsPagination],
)
async def get_gongkao_category_list(
    db: CurrentSession,
    name: Annotated[str | None, Query(description='分类名称')] = None,
    category_type: Annotated[str | None, Query(description='分类类型', alias='type')] = None,
    parent_id: Annotated[int | None, Query(description='父级分类 ID')] = None,
    status: Annotated[bool | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[PageData[GetCategoryDetail]]:
    """获取分类列表（分页）"""
    params = CategoryParam(
        name=name,
        type=category_type,
        parent_id=parent_id,
        status=status,
    )
    data = await category_service.get_list(db=db, params=params)
    return response_base.success(data=data)


@router.post(
    '',
    summary='创建分类',
    dependencies=[
        Depends(RequestPermission('gongkao:category:create')),
        DependsRBAC,
    ],
)
async def create_gongkao_category(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateCategoryParam,
) -> ResponseModel:
    """创建分类"""
    await category_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新分类',
    dependencies=[
        Depends(RequestPermission('gongkao:category:update')),
        DependsRBAC,
    ],
)
async def update_gongkao_category(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='分类 ID')],
    obj: UpdateCategoryParam,
) -> ResponseModel:
    """更新分类"""
    count = await category_service.update(db=db, pk=pk, obj=obj, updated_by=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '',
    summary='删除分类',
    dependencies=[
        Depends(RequestPermission('gongkao:category:delete')),
        DependsRBAC,
    ],
)
async def delete_gongkao_category(db: CurrentSessionTransaction, obj: DeleteCategoryParam) -> ResponseModel:
    """删除分类"""
    count = await category_service.delete(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()
