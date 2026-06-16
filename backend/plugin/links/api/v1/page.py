#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Query, Request

from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction
from backend.plugin.links.schema import (
    CreatePageParam,
    GetPageDetail,
    GetPageList,
    LogStatistics,
    UpdatePageParam,
)
from backend.plugin.links.service import page_service

router = APIRouter()


@router.get('', summary='获取页面列表', dependencies=[DependsJwtAuth, DependsPagination])
async def get_page_list(
    db: CurrentSession,
    request: Request,
    title: Annotated[str | None, Query(description='标题模糊搜索')] = None,
    status: Annotated[int | None, Query(ge=0, le=1, description='状态筛选')] = None,
) -> ResponseSchemaModel[PageData[GetPageList]]:
    select = page_service.get_select(title=title, status=status, created_by=request.user.id)
    page_data = await paging_data(db, select)
    return response_base.success(data=page_data)


@router.get('/{pk}', summary='获取页面详情', dependencies=[DependsJwtAuth])
async def get_page_detail(db: CurrentSession, pk: int) -> ResponseSchemaModel[GetPageDetail]:
    page = await page_service.get(db=db, pk=pk)
    return response_base.success(data=GetPageDetail.model_validate(page))


@router.get('/{pk}/statistics', summary='获取页面统计', dependencies=[DependsJwtAuth])
async def get_page_statistics(db: CurrentSession, pk: int) -> ResponseSchemaModel[LogStatistics]:
    statistics = await page_service.get_statistics(db=db, pk=pk)
    return response_base.success(data=statistics)


@router.post('', summary='创建页面', dependencies=[DependsJwtAuth])
async def create_page(
    db: CurrentSessionTransaction,
    request: Request,
    obj: CreatePageParam,
) -> ResponseSchemaModel[GetPageDetail]:
    page = await page_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success(data=GetPageDetail.model_validate(page))


@router.put('/{pk}', summary='更新页面', dependencies=[DependsJwtAuth])
async def update_page(db: CurrentSessionTransaction, pk: int, obj: UpdatePageParam) -> ResponseModel:
    await page_service.update(db=db, pk=pk, obj=obj)
    return response_base.success()


@router.delete('/{pk}', summary='删除页面', dependencies=[DependsJwtAuth])
async def delete_page(db: CurrentSessionTransaction, pk: int) -> ResponseModel:
    await page_service.delete(db=db, pk=pk)
    return response_base.success()
