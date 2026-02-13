#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.app.jia.schema.food import CreateFoodParam, GetFoodDetail, UpdateFoodParam
from backend.app.jia.service.food_service import food_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get(
    '',
    summary='获取食物列表',
    dependencies=[
        DependsJwtAuth,
        DependsPagination,
    ],
)
async def get_all_foods(
    db: CurrentSession,
    name: Annotated[str | None, Query(description='名称/搜索关键词')] = None,
    category_id: Annotated[int | None, Query(description='分类 ID')] = None,
    status: Annotated[bool | None, Query(description='状态')] = None,
    semantic: Annotated[bool, Query(description='是否启用语义搜索（启用时忽略分页）')] = False,
    limit: Annotated[int, Query(description='语义搜索返回数量', ge=1, le=100)] = 20,
) -> ResponseSchemaModel[PageData[GetFoodDetail] | list[GetFoodDetail]]:
    food_page = await food_service.get_list(
        db=db,
        name=name,
        category_id=category_id,
        status=status,
        semantic=semantic,
        limit=limit,
    )
    return response_base.success(data=food_page)


@router.get(
    '/{pk}',
    summary='获取食物详情',
    dependencies=[
        DependsJwtAuth,
    ],
)
async def get_food(
    pk: Annotated[int, Path(...)],
    db: CurrentSession,
) -> ResponseSchemaModel[GetFoodDetail]:
    food = await food_service.get(db=db, pk=pk)
    return response_base.success(data=food)


@router.post(
    '',
    summary='创建食物',
    dependencies=[
        Depends(RequestPermission('jia:food:add')),
        DependsRBAC,
    ],
)
async def create_food(
    obj: CreateFoodParam,
    db: CurrentSessionTransaction,
) -> ResponseModel:
    await food_service.create(db=db, obj=obj)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新食物',
    dependencies=[
        Depends(RequestPermission('jia:food:edit')),
        DependsRBAC,
    ],
)
async def update_food(
    pk: Annotated[int, Path(...)],
    obj: UpdateFoodParam,
    db: CurrentSessionTransaction,
) -> ResponseModel:
    count = await food_service.update(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '',
    summary='批量删除食物',
    dependencies=[
        Depends(RequestPermission('jia:food:del')),
        DependsRBAC,
    ],
)
async def delete_food(
    pk: Annotated[list[int], Query(...)],
    db: CurrentSessionTransaction,
) -> ResponseModel:
    count = await food_service.delete(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
