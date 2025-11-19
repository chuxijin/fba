#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.jia.schema.category import (
    CreateCategoryParam,
    DeleteCategoryParam,
    GetCategoryDetail,
    UpdateCategoryParam,
)
from backend.app.jia.service.category_service import category_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='获取分类详情', dependencies=[DependsJwtAuth])
async def get_jia_category(
    db: CurrentSession, pk: Annotated[int, Path(description='分类 ID')]
) -> ResponseSchemaModel[GetCategoryDetail]:
    data = await category_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('', summary='获取分类列表', dependencies=[DependsJwtAuth])
async def get_jia_category_list(
    db: CurrentSession,
    parent_id: Annotated[int | None, Query(description='父级分类 ID')] = None,
    name: Annotated[str | None, Query(description='分类名称')] = None,
    sync_status: Annotated[str | None, Query(description='同步状态')] = None,
) -> ResponseSchemaModel[list[GetCategoryDetail]]:
    data = await category_service.get_list(db=db, parent_id=parent_id, name=name, sync_status=sync_status)
    return response_base.success(data=data)


@router.get('/all', summary='获取所有分类', dependencies=[DependsJwtAuth])
async def get_all_jia_categories(db: CurrentSession, request: Request) -> ResponseSchemaModel[list[GetCategoryDetail]]:
    data = await category_service.get_all(db=db, user_id=request.user.id)
    return response_base.success(data=data)


@router.get('/{pk}/children', summary='获取子分类列表', dependencies=[DependsJwtAuth])
async def get_jia_category_children(
    db: CurrentSession, pk: Annotated[int, Path(description='父级分类 ID')]
) -> ResponseSchemaModel[list[GetCategoryDetail]]:
    data = await category_service.get_children(db=db, parent_id=pk)
    return response_base.success(data=data)


@router.post('', summary='创建分类', dependencies=[DependsJwtAuth])
async def create_jia_category(
    db: CurrentSessionTransaction, request: Request, obj: CreateCategoryParam
) -> ResponseModel:
    await category_service.create(db=db, obj=obj, user_id=request.user.id)
    return response_base.success()


@router.put('/{pk}', summary='更新分类', dependencies=[DependsJwtAuth])
async def update_jia_category(
    db: CurrentSessionTransaction,
    request: Request,
    pk: Annotated[int, Path(description='分类 ID')],
    obj: UpdateCategoryParam,
) -> ResponseModel:
    count = await category_service.update(db=db, pk=pk, obj=obj, user_id=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('', summary='批量删除分类', dependencies=[DependsJwtAuth])
async def delete_jia_category(db: CurrentSessionTransaction, obj: DeleteCategoryParam) -> ResponseModel:
    count = await category_service.delete(db=db, pks=obj.pks)
    if count > 0:
        return response_base.success()
    return response_base.fail()

