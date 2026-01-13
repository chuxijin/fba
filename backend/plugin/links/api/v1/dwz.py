#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Query, Request

from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction
from backend.plugin.links.schema import CreateDwzParam, GetDwzDetail, GetDwzList, LogStatistics, UpdateDwzParam
from backend.plugin.links.service import dwz_service

router = APIRouter()


@router.get('', summary='获取短网址列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_dwz_list(
    db: CurrentSession,
    request: Request,
    title: Annotated[str | None, Query(description='标题模糊搜索')] = None,
    status: Annotated[int | None, Query(ge=0, le=1, description='状态筛选')] = None,
) -> ResponseSchemaModel[PageData[GetDwzList]]:
    select = dwz_service.get_select(title=title, status=status, created_by=request.user.id)
    page_data = await paging_data(db, select)
    return response_base.success(data=page_data)


@router.get('/{pk}', summary='获取短网址详情', dependencies=[DependsJwtAuth])
async def get_dwz_detail(db: CurrentSession, pk: int) -> ResponseSchemaModel[GetDwzDetail]:
    dwz = await dwz_service.get(db=db, pk=pk)
    return response_base.success(data=GetDwzDetail.model_validate(dwz))


@router.get('/{pk}/statistics', summary='获取短网址统计', dependencies=[DependsJwtAuth])
async def get_dwz_statistics(db: CurrentSession, pk: int) -> ResponseSchemaModel[LogStatistics]:
    statistics = await dwz_service.get_statistics(db=db, pk=pk)
    return response_base.success(data=statistics)


@router.post('', summary='创建短网址', dependencies=[DependsJwtAuth])
async def create_dwz(
    db: CurrentSessionTransaction,
    request: Request,
    obj: CreateDwzParam,
) -> ResponseSchemaModel[GetDwzDetail]:
    dwz = await dwz_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success(data=GetDwzDetail.model_validate(dwz))


@router.put('/{pk}', summary='更新短网址', dependencies=[DependsJwtAuth])
async def update_dwz(db: CurrentSessionTransaction, pk: int, obj: UpdateDwzParam) -> ResponseModel:
    await dwz_service.update(db=db, pk=pk, obj=obj)
    return response_base.success()


@router.delete('/{pk}', summary='删除短网址', dependencies=[DependsJwtAuth])
async def delete_dwz(db: CurrentSessionTransaction, pk: int) -> ResponseModel:
    await dwz_service.delete(db=db, pk=pk)
    return response_base.success()
