#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.app.gongkao.schema.guanmei import (
    CreateGuanmeiParam,
    DeleteGuanmeiParam,
    GetGuanmeiDetail,
    GuanmeiParam,
    UpdateGuanmeiParam,
)
from backend.app.gongkao.service.guanmei_service import guanmei_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='获取官媒学言语详情')
async def get_guanmei(
    db: CurrentSession, pk: Annotated[int, Path(description='ID')]
) -> ResponseSchemaModel[GetGuanmeiDetail]:
    """获取详情"""
    data = await guanmei_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get(
    '',
    summary='获取官媒学言语列表',
    dependencies=[DependsPagination],
)
async def get_guanmei_list(
    db: CurrentSession,
    daily_date: Annotated[str | None, Query(description='日期')] = None,
) -> ResponseSchemaModel[PageData[GetGuanmeiDetail]]:
    """获取列表（分页）"""
    from datetime import date as date_type

    params = GuanmeiParam(
        daily_date=date_type.fromisoformat(daily_date) if daily_date else None,
    )
    data = await guanmei_service.get_list(db=db, params=params)
    return response_base.success(data=data)


@router.post(
    '',
    summary='创建官媒学言语',
    dependencies=[
        Depends(RequestPermission('gongkao:guanmei:create')),
        DependsRBAC,
    ],
)
async def create_guanmei(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateGuanmeiParam,
) -> ResponseModel:
    """创建"""
    await guanmei_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新官媒学言语',
    dependencies=[
        Depends(RequestPermission('gongkao:guanmei:update')),
        DependsRBAC,
    ],
)
async def update_guanmei(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='ID')],
    obj: UpdateGuanmeiParam,
) -> ResponseModel:
    """更新"""
    count = await guanmei_service.update(db=db, pk=pk, obj=obj, updated_by=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '',
    summary='删除官媒学言语',
    dependencies=[
        Depends(RequestPermission('gongkao:guanmei:delete')),
        DependsRBAC,
    ],
)
async def delete_guanmei(db: CurrentSessionTransaction, obj: DeleteGuanmeiParam) -> ResponseModel:
    """删除"""
    count = await guanmei_service.delete(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.post('/{pk}/view', summary='增加阅读量')
async def increment_guanmei_view(
    db: CurrentSessionTransaction, pk: Annotated[int, Path(description='ID')]
) -> ResponseModel:
    """增加阅读量"""
    await guanmei_service.increment_view(db=db, pk=pk)
    return response_base.success()
