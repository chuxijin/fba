#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Query, Request

from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction
from backend.plugin.links.schema import (
    CreateQunItemParam,
    CreateQunParam,
    GetQunDetail,
    GetQunItemDetail,
    GetQunList,
    LogStatistics,
    UpdateQunItemParam,
    UpdateQunParam,
)
from backend.plugin.links.service import qun_item_service, qun_service

router = APIRouter()


# ==================== 群活码主表 ====================
@router.get('', summary='获取群活码列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_qun_list(
    db: CurrentSession,
    request: Request,
    title: Annotated[str | None, Query(description='标题模糊搜索')] = None,
    status: Annotated[int | None, Query(ge=0, le=1, description='状态筛选')] = None,
) -> ResponseSchemaModel[PageData[GetQunList]]:
    select = qun_service.get_select(title=title, status=status, created_by=request.user.id)
    page_data = await paging_data(db, select)
    return response_base.success(data=page_data)


@router.get('/{pk}', summary='获取群活码详情', dependencies=[DependsJwtAuth])
async def get_qun_detail(db: CurrentSession, pk: int) -> ResponseSchemaModel[GetQunDetail]:
    qun = await qun_service.get(db=db, pk=pk)
    return response_base.success(data=GetQunDetail.model_validate(qun))


@router.get('/{pk}/statistics', summary='获取群活码统计', dependencies=[DependsJwtAuth])
async def get_qun_statistics(db: CurrentSession, pk: int) -> ResponseSchemaModel[LogStatistics]:
    statistics = await qun_service.get_statistics(db=db, pk=pk)
    return response_base.success(data=statistics)


@router.get('/{pk}/items', summary='获取群活码子项列表', dependencies=[DependsJwtAuth])
async def get_qun_items(db: CurrentSession, pk: int) -> ResponseSchemaModel[list[GetQunItemDetail]]:
    items = await qun_item_service.get_by_qun_id(db=db, qun_id=pk)
    return response_base.success(data=[GetQunItemDetail.model_validate(item) for item in items])


@router.post('', summary='创建群活码', dependencies=[DependsJwtAuth])
async def create_qun(
    db: CurrentSessionTransaction,
    request: Request,
    obj: CreateQunParam,
) -> ResponseSchemaModel[GetQunDetail]:
    qun = await qun_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success(data=GetQunDetail.model_validate(qun))


@router.put('/{pk}', summary='更新群活码', dependencies=[DependsJwtAuth])
async def update_qun(db: CurrentSessionTransaction, pk: int, obj: UpdateQunParam) -> ResponseModel:
    await qun_service.update(db=db, pk=pk, obj=obj)
    return response_base.success()


@router.delete('/{pk}', summary='删除群活码', dependencies=[DependsJwtAuth])
async def delete_qun(db: CurrentSessionTransaction, pk: int) -> ResponseModel:
    await qun_service.delete(db=db, pk=pk)
    return response_base.success()


# ==================== 群活码子表 ====================
@router.post('/item', summary='创建群活码子项', dependencies=[DependsJwtAuth])
async def create_qun_item(
    db: CurrentSessionTransaction,
    request: Request,
    obj: CreateQunItemParam,
) -> ResponseSchemaModel[GetQunItemDetail]:
    item = await qun_item_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success(data=GetQunItemDetail.model_validate(item))


@router.put('/item/{pk}', summary='更新群活码子项', dependencies=[DependsJwtAuth])
async def update_qun_item(db: CurrentSessionTransaction, pk: int, obj: UpdateQunItemParam) -> ResponseModel:
    await qun_item_service.update(db=db, pk=pk, obj=obj)
    return response_base.success()


@router.delete('/item/{pk}', summary='删除群活码子项', dependencies=[DependsJwtAuth])
async def delete_qun_item(db: CurrentSessionTransaction, pk: int) -> ResponseModel:
    await qun_item_service.delete(db=db, pk=pk)
    return response_base.success()
