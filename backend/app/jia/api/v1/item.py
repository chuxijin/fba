#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.jia.schema import CreateItemParam, GetItemDetail, GetItemList, UpdateItemParam
from backend.app.jia.service import item_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get(
    '',
    summary='获取物品列表',
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def get_items_paginated(
    request: Request,
    db: CurrentSession,
    ids: Annotated[list[int] | None, Query(description='物品 ID 列表')] = None,
    name: Annotated[str | None, Query(description='物品名称/搜索关键词')] = None,
    category: Annotated[str | None, Query(description='分类')] = None,
    status: Annotated[str | None, Query(description='状态')] = None,
    location: Annotated[str | None, Query(description='存放位置')] = None,
    semantic: Annotated[bool, Query(description='是否启用语义搜索（启用时忽略分页）')] = False,
    limit: Annotated[int, Query(description='语义搜索返回数量', ge=1, le=100)] = 20,
) -> ResponseSchemaModel[PageData[GetItemList] | list[GetItemList]]:
    """获取当前用户的物品列表"""
    user_id = request.user.id
    page_data = await item_service.get_list(
        db=db,
        user_id=user_id,
        ids=ids,
        name=name,
        category=category,
        status=status,
        location=location,
        semantic=semantic,
        limit=limit,
    )
    return response_base.success(data=page_data)


@router.get('/categories', summary='获取分类列表', dependencies=[DependsJwtAuth])
async def get_categories(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[list[str]]:
    """获取当前用户的所有物品分类"""
    user_id = request.user.id
    categories = await item_service.get_categories(db=db, user_id=user_id)
    return response_base.success(data=categories)


@router.get('/stats', summary='获取状态统计', dependencies=[DependsJwtAuth])
async def get_status_stats(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[dict[str, int]]:
    """获取当前用户的物品状态统计"""
    user_id = request.user.id
    stats = await item_service.get_status_stats(db=db, user_id=user_id)
    return response_base.success(data=stats)


@router.get('/{pk}', summary='获取物品详情', dependencies=[DependsJwtAuth])
async def get_item(
    request: Request,
    db: CurrentSession,
    pk: Annotated[int, Path(description='物品 ID')],
) -> ResponseSchemaModel[GetItemDetail]:
    """获取物品详情"""
    user_id = request.user.id
    item = await item_service.get(db=db, pk=pk, user_id=user_id)
    return response_base.success(data=item)


@router.post('', summary='创建物品', dependencies=[DependsJwtAuth])
async def create_item(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateItemParam,
) -> ResponseSchemaModel[GetItemDetail]:
    """创建新物品"""
    user_id = request.user.id
    item = await item_service.create(db=db, obj=obj, user_id=user_id)
    return response_base.success(data=item)


@router.put('/{pk}', summary='更新物品', dependencies=[DependsJwtAuth])
async def update_item(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='物品 ID')],
    obj: UpdateItemParam,
) -> ResponseModel:
    """更新物品信息"""
    user_id = request.user.id
    count = await item_service.update(db=db, pk=pk, obj=obj, user_id=user_id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('', summary='删除物品', dependencies=[DependsJwtAuth])
async def delete_items(
    request: Request,
    db: CurrentSessionTransaction,
    pks: Annotated[list[int], Query(description='物品 ID 列表')],
) -> ResponseSchemaModel[int]:
    """删除物品（支持单个和批量）"""
    user_id = request.user.id
    count = await item_service.delete(db=db, pks=pks, user_id=user_id)
    return response_base.success(data=count)
