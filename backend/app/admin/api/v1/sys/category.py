#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.app.admin.schema.category import (
    CreateCategoryParam,
    DeleteCategoryParam,
    GetCategoryDetail,
    GetCategoryTree,
    UpdateCategoryParam,
)
from backend.app.admin.service.category_service import category_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/tree', summary='获取分类树', dependencies=[DependsJwtAuth])
async def get_sys_category_tree(
    db: CurrentSession,
    app_code: Annotated[str | None, Query(description='应用标识')] = None,
    type_: Annotated[str | None, Query(alias='type', description='分类类型')] = None,
    name: Annotated[str | None, Query(description='分类名称')] = None,
    status: Annotated[bool | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[list[GetCategoryTree]]:
    tree = await category_service.get_tree(db=db, app_code=app_code, type_=type_, name=name, status=status)
    return response_base.success(data=tree)


@router.get(
    '',
    summary='分页获取分类列表',
    dependencies=[
        DependsJwtAuth,
        DependsPagination,
    ],
)
async def get_sys_category_list(
    db: CurrentSession,
    app_code: Annotated[str | None, Query(description='应用标识')] = None,
    type_: Annotated[str | None, Query(alias='type', description='分类类型')] = None,
    name: Annotated[str | None, Query(description='分类名称')] = None,
    status: Annotated[bool | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[PageData[GetCategoryDetail]]:
    page_data = await category_service.get_list(db=db, app_code=app_code, type_=type_, name=name, status=status)
    return response_base.success(data=page_data)


@router.get('/types/{app_code}', summary='获取应用分类类型列表', dependencies=[DependsJwtAuth])
async def get_sys_category_types(
    db: CurrentSession,
    app_code: Annotated[str, Path(description='应用标识')],
) -> ResponseSchemaModel[list[str]]:
    types = await category_service.get_app_types(db=db, app_code=app_code)
    return response_base.success(data=types)


@router.get('/options/app-codes', summary='获取所有应用标识选项', dependencies=[DependsJwtAuth])
async def get_sys_category_app_codes(db: CurrentSession) -> ResponseSchemaModel[list[str]]:
    app_codes = await category_service.get_all_app_codes(db=db)
    return response_base.success(data=app_codes)


@router.get('/options/types', summary='获取所有分类类型选项', dependencies=[DependsJwtAuth])
async def get_sys_category_type_options(
    db: CurrentSession,
    app_code: Annotated[str | None, Query(description='应用标识（可选）')] = None,
) -> ResponseSchemaModel[list[str]]:
    types = await category_service.get_all_types(db=db, app_code=app_code)
    return response_base.success(data=types)


@router.get('/{pk}', summary='获取分类详情', dependencies=[DependsJwtAuth])
async def get_sys_category(
    db: CurrentSession,
    pk: Annotated[int, Path(description='分类 ID')],
) -> ResponseSchemaModel[GetCategoryDetail]:
    category = await category_service.get(db=db, pk=pk)
    return response_base.success(data=category)


@router.post(
    '',
    summary='创建分类',
    dependencies=[
        Depends(RequestPermission('sys:category:add')),
        DependsRBAC,
    ],
)
async def create_sys_category(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateCategoryParam,
) -> ResponseModel:
    await category_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新分类',
    dependencies=[
        Depends(RequestPermission('sys:category:edit')),
        DependsRBAC,
    ],
)
async def update_sys_category(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='分类 ID')],
    obj: UpdateCategoryParam,
) -> ResponseModel:
    count = await category_service.update(db=db, pk=pk, obj=obj, updated_by=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '',
    summary='批量删除分类',
    dependencies=[
        Depends(RequestPermission('sys:category:del')),
        DependsRBAC,
    ],
)
async def delete_sys_categories(
    db: CurrentSessionTransaction,
    obj: DeleteCategoryParam,
) -> ResponseModel:
    count = await category_service.delete_batch(db=db, ids=obj.ids)
    if count > 0:
        return response_base.success()
    return response_base.fail()
