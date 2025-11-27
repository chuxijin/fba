#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.app.health.schema.food import CreateFoodParam, GetFoodDetail, UpdateFoodParam
from backend.app.health.service.food_service import food_service
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='获取食物详情', dependencies=[DependsJwtAuth])
async def get_food(
    db: CurrentSession, pk: Annotated[int, Path(description='食物 ID')]
) -> ResponseSchemaModel[GetFoodDetail]:
    """获取食物详情"""
    data = await food_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('', summary='分页获取食物列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_foods_paginated(
    db: CurrentSession,
    name: Annotated[str | None, Query(description='食物名称')] = None,
    category_id: Annotated[int | None, Query(description='分类 ID')] = None,
    food_type: Annotated[int | None, Query(description='食物类型')] = None,
    processing_level: Annotated[int | None, Query(description='加工程度')] = None,
    status: Annotated[int | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[PageData[GetFoodDetail]]:
    """分页获取食物列表"""
    select_stmt = await food_service.get_select(
        name=name, category_id=category_id, food_type=food_type, processing_level=processing_level, status=status
    )
    page_data = await paging_data(db, select_stmt, GetFoodDetail)
    return response_base.success(data=page_data)


@router.post('', summary='创建食物', dependencies=[DependsJwtAuth])
async def create_food(db: CurrentSessionTransaction, obj: CreateFoodParam) -> ResponseModel:
    """创建食物"""
    await food_service.create(db=db, obj=obj)
    return response_base.success()


@router.put('/{pk}', summary='更新食物', dependencies=[DependsJwtAuth])
async def update_food(
    db: CurrentSessionTransaction, pk: Annotated[int, Path(description='食物 ID')], obj: UpdateFoodParam
) -> ResponseModel:
    """更新食物"""
    count = await food_service.update(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/{pk}', summary='删除食物', dependencies=[DependsJwtAuth])
async def delete_food(db: CurrentSessionTransaction, pk: Annotated[int, Path(description='食物 ID')]) -> ResponseModel:
    """删除食物"""
    count = await food_service.delete(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
