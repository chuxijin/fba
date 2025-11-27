#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query

from backend.app.health.schema.food_category import (
    CreateFoodCategoryParam,
    GetFoodCategoryDetail,
    GetFoodCategoryTree,
    UpdateFoodCategoryParam,
)
from backend.app.health.service.food_category_service import food_category_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='获取食物分类详情', dependencies=[DependsJwtAuth])
async def get_food_category(
    db: CurrentSession, pk: Annotated[int, Path(description='分类 ID')]
) -> ResponseSchemaModel[GetFoodCategoryDetail]:
    """获取食物分类详情"""
    data = await food_category_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('', summary='获取食物分类树', dependencies=[DependsJwtAuth])
async def get_food_category_tree(
    db: CurrentSession,
    name: Annotated[str | None, Query(description='分类名称')] = None,
    status: Annotated[int | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[list[GetFoodCategoryTree]]:
    """获取食物分类树形结构"""
    data = await food_category_service.get_tree(db=db, name=name, status=status)
    return response_base.success(data=data)


@router.post('', summary='创建食物分类', dependencies=[DependsJwtAuth])
async def create_food_category(db: CurrentSessionTransaction, obj: CreateFoodCategoryParam) -> ResponseModel:
    """创建食物分类"""
    await food_category_service.create(db=db, obj=obj)
    return response_base.success()


@router.put('/{pk}', summary='更新食物分类', dependencies=[DependsJwtAuth])
async def update_food_category(
    db: CurrentSessionTransaction, pk: Annotated[int, Path(description='分类 ID')], obj: UpdateFoodCategoryParam
) -> ResponseModel:
    """更新食物分类"""
    count = await food_category_service.update(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/{pk}', summary='删除食物分类', dependencies=[DependsJwtAuth])
async def delete_food_category(
    db: CurrentSessionTransaction, pk: Annotated[int, Path(description='分类 ID')]
) -> ResponseModel:
    """删除食物分类"""
    count = await food_category_service.delete(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
