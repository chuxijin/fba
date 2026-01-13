#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Query, Request

from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction
from backend.plugin.links.schema import (
    CreateKfItemParam,
    CreateKfParam,
    GetKfDetail,
    GetKfItemDetail,
    GetKfList,
    LogStatistics,
    UpdateKfItemParam,
    UpdateKfParam,
)
from backend.plugin.links.service import kf_item_service, kf_service

router = APIRouter()


# ==================== 客服码主表 ====================
@router.get('', summary='获取客服码列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_kf_list(
    db: CurrentSession,
    request: Request,
    title: Annotated[str | None, Query(description='标题模糊搜索')] = None,
    status: Annotated[int | None, Query(ge=0, le=1, description='状态筛选')] = None,
) -> ResponseSchemaModel[PageData[GetKfList]]:
    select = kf_service.get_select(title=title, status=status, created_by=request.user.id)
    page_data = await paging_data(db, select)
    return response_base.success(data=page_data)


@router.get('/{pk}', summary='获取客服码详情', dependencies=[DependsJwtAuth])
async def get_kf_detail(db: CurrentSession, pk: int) -> ResponseSchemaModel[GetKfDetail]:
    kf = await kf_service.get(db=db, pk=pk)
    return response_base.success(data=GetKfDetail.model_validate(kf))


@router.get('/{pk}/statistics', summary='获取客服码统计', dependencies=[DependsJwtAuth])
async def get_kf_statistics(db: CurrentSession, pk: int) -> ResponseSchemaModel[LogStatistics]:
    statistics = await kf_service.get_statistics(db=db, pk=pk)
    return response_base.success(data=statistics)


@router.get('/{pk}/items', summary='获取客服码子项列表', dependencies=[DependsJwtAuth])
async def get_kf_items(db: CurrentSession, pk: int) -> ResponseSchemaModel[list[GetKfItemDetail]]:
    items = await kf_item_service.get_by_kf_id(db=db, kf_id=pk)
    return response_base.success(data=[GetKfItemDetail.model_validate(item) for item in items])


@router.post('', summary='创建客服码', dependencies=[DependsJwtAuth])
async def create_kf(
    db: CurrentSessionTransaction,
    request: Request,
    obj: CreateKfParam,
) -> ResponseSchemaModel[GetKfDetail]:
    kf = await kf_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success(data=GetKfDetail.model_validate(kf))


@router.put('/{pk}', summary='更新客服码', dependencies=[DependsJwtAuth])
async def update_kf(db: CurrentSessionTransaction, pk: int, obj: UpdateKfParam) -> ResponseModel:
    await kf_service.update(db=db, pk=pk, obj=obj)
    return response_base.success()


@router.delete('/{pk}', summary='删除客服码', dependencies=[DependsJwtAuth])
async def delete_kf(db: CurrentSessionTransaction, pk: int) -> ResponseModel:
    await kf_service.delete(db=db, pk=pk)
    return response_base.success()


# ==================== 客服码子表 ====================
@router.post('/item', summary='创建客服码子项', dependencies=[DependsJwtAuth])
async def create_kf_item(
    db: CurrentSessionTransaction,
    request: Request,
    obj: CreateKfItemParam,
) -> ResponseSchemaModel[GetKfItemDetail]:
    item = await kf_item_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success(data=GetKfItemDetail.model_validate(item))


@router.put('/item/{pk}', summary='更新客服码子项', dependencies=[DependsJwtAuth])
async def update_kf_item(db: CurrentSessionTransaction, pk: int, obj: UpdateKfItemParam) -> ResponseModel:
    await kf_item_service.update(db=db, pk=pk, obj=obj)
    return response_base.success()


@router.delete('/item/{pk}', summary='删除客服码子项', dependencies=[DependsJwtAuth])
async def delete_kf_item(db: CurrentSessionTransaction, pk: int) -> ResponseModel:
    await kf_item_service.delete(db=db, pk=pk)
    return response_base.success()
