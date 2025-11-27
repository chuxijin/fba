#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.app.health.schema.food_tag import (
    AddFoodTagRelationParam,
    CreateFoodTagParam,
    GetFoodTagDetail,
    RemoveFoodTagRelationParam,
    UpdateFoodTagParam,
)
from backend.app.health.service.food_tag_service import food_tag_service
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='获取食物标签详情', dependencies=[DependsJwtAuth])
async def get_food_tag(
    db: CurrentSession, pk: Annotated[int, Path(description='标签 ID')]
) -> ResponseSchemaModel[GetFoodTagDetail]:
    """获取食物标签详情"""
    data = await food_tag_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get('', summary='分页获取食物标签列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_food_tags_paginated(
    db: CurrentSession,
    name: Annotated[str | None, Query(description='标签名称')] = None,
    tag_group: Annotated[int | None, Query(description='标签分组')] = None,
    status: Annotated[int | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[PageData[GetFoodTagDetail]]:
    """分页获取食物标签列表"""
    select_stmt = await food_tag_service.get_select(name=name, tag_group=tag_group, status=status)
    page_data = await paging_data(db, select_stmt, GetFoodTagDetail)
    return response_base.success(data=page_data)


@router.get('/food/{food_id}', summary='获取食物的所有标签', dependencies=[DependsJwtAuth])
async def get_food_tags_by_food(
    db: CurrentSession, food_id: Annotated[int, Path(description='食物 ID')]
) -> ResponseSchemaModel[list[GetFoodTagDetail]]:
    """获取食物的所有标签"""
    data = await food_tag_service.get_food_tags(db=db, food_id=food_id)
    return response_base.success(data=data)


@router.post('', summary='创建食物标签', dependencies=[DependsJwtAuth])
async def create_food_tag(db: CurrentSessionTransaction, obj: CreateFoodTagParam) -> ResponseModel:
    """创建食物标签"""
    await food_tag_service.create(db=db, obj=obj)
    return response_base.success()


@router.post('/relation', summary='为食物添加标签', dependencies=[DependsJwtAuth])
async def add_food_tag_relation(db: CurrentSessionTransaction, obj: AddFoodTagRelationParam) -> ResponseModel:
    """为食物添加标签"""
    await food_tag_service.add_food_tags(db=db, obj=obj)
    return response_base.success()


@router.delete('/relation', summary='移除食物的标签', dependencies=[DependsJwtAuth])
async def remove_food_tag_relation(db: CurrentSessionTransaction, obj: RemoveFoodTagRelationParam) -> ResponseModel:
    """移除食物的标签"""
    await food_tag_service.remove_food_tags(db=db, obj=obj)
    return response_base.success()


@router.put('/{pk}', summary='更新食物标签', dependencies=[DependsJwtAuth])
async def update_food_tag(
    db: CurrentSessionTransaction, pk: Annotated[int, Path(description='标签 ID')], obj: UpdateFoodTagParam
) -> ResponseModel:
    """更新食物标签"""
    count = await food_tag_service.update(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete('/{pk}', summary='删除食物标签', dependencies=[DependsJwtAuth])
async def delete_food_tag(
    db: CurrentSessionTransaction, pk: Annotated[int, Path(description='标签 ID')]
) -> ResponseModel:
    """删除食物标签"""
    count = await food_tag_service.delete(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
