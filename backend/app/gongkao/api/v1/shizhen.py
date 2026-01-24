#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.app.gongkao.schema.shizhen import (
    CreateShizhenParam,
    DeleteShizhenParam,
    GetShizhenDetail,
    ShizhenParam,
    UpdateShizhenParam,
)
from backend.app.gongkao.service.shizhen_service import shizhen_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='获取时政详情')
async def get_shizhen(
    db: CurrentSession, pk: Annotated[int, Path(description='时政 ID')]
) -> ResponseSchemaModel[GetShizhenDetail]:
    """获取时政详情"""
    data = await shizhen_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get(
    '',
    summary='获取时政列表',
    dependencies=[DependsPagination],
)
async def get_shizhen_list(
    db: CurrentSession,
    daily_date: Annotated[str | None, Query(description='日期')] = None,
) -> ResponseSchemaModel[PageData[GetShizhenDetail]]:
    """获取时政列表（分页）"""
    from datetime import date as date_type

    params = ShizhenParam(
        daily_date=date_type.fromisoformat(daily_date) if daily_date else None,
    )
    data = await shizhen_service.get_list(db=db, params=params)
    return response_base.success(data=data)


@router.post(
    '',
    summary='创建时政',
    dependencies=[
        Depends(RequestPermission('gongkao:shizhen:create')),
        DependsRBAC,
    ],
)
async def create_shizhen(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateShizhenParam,
) -> ResponseModel:
    """创建时政"""
    await shizhen_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新时政',
    dependencies=[
        Depends(RequestPermission('gongkao:shizhen:update')),
        DependsRBAC,
    ],
)
async def update_shizhen(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='时政 ID')],
    obj: UpdateShizhenParam,
) -> ResponseModel:
    """更新时政"""
    count = await shizhen_service.update(db=db, pk=pk, obj=obj, updated_by=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '',
    summary='删除时政',
    dependencies=[
        Depends(RequestPermission('gongkao:shizhen:delete')),
        DependsRBAC,
    ],
)
async def delete_shizhen(db: CurrentSessionTransaction, obj: DeleteShizhenParam) -> ResponseModel:
    """删除时政"""
    count = await shizhen_service.delete(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()
