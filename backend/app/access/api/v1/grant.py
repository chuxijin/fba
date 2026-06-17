#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.app.access.constants import CommonStatus, GrantSource
from backend.app.access.schema.grant import (
    CreateDirectGrantParam,
    GetDirectGrantDetail,
)
from backend.app.access.service.grant_service import direct_grant_service
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get(
    '/{pk}',
    summary='获取授予详情',
    dependencies=[
        Depends(RequestPermission('access:grant:query')),
        DependsRBAC,
    ],
)
async def get_grant(
    db: CurrentSession,
    pk: Annotated[int, Path(description='授予 ID')],
) -> ResponseSchemaModel[GetDirectGrantDetail]:
    """获取授予详情"""
    data = await direct_grant_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get(
    '',
    summary='分页查询授予',
    dependencies=[
        Depends(RequestPermission('access:grant:query')),
        DependsRBAC,
        DependsPagination,
    ],
)
async def get_grant_list(
    db: CurrentSession,
    user_id: Annotated[int | None, Query(description='用户 ID')] = None,
    entitlement_code: Annotated[str | None, Query(description='权益编码')] = None,
    source: Annotated[GrantSource | None, Query(description='来源')] = None,
    status: Annotated[CommonStatus | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[PageData[GetDirectGrantDetail]]:
    """分页查询授予"""
    stmt = await direct_grant_service.get_select(
        user_id=user_id,
        entitlement_code=entitlement_code,
        source=source,
        status=status,
    )
    page_data = await paging_data(db, stmt)
    return response_base.success(data=page_data)


@router.post(
    '',
    summary='创建直接授予',
    dependencies=[
        Depends(RequestPermission('access:grant:create')),
        DependsRBAC,
    ],
)
async def create_grant(db: CurrentSessionTransaction, obj: CreateDirectGrantParam) -> ResponseModel:
    """创建直接授予"""
    await direct_grant_service.create(db=db, obj=obj)
    return response_base.success()


@router.delete(
    '/{pk}',
    summary='撤销授予',
    dependencies=[
        Depends(RequestPermission('access:grant:delete')),
        DependsRBAC,
    ],
)
async def revoke_grant(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='授予 ID')],
) -> ResponseModel:
    """撤销授予"""
    count = await direct_grant_service.revoke(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
