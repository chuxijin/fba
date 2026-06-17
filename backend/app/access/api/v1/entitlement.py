#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.app.access.constants import CommonStatus, EntitlementCategory, EntitlementVerb
from backend.app.access.schema.entitlement import (
    CreateEntitlementParam,
    GetEntitlementDetail,
    UpdateEntitlementParam,
)
from backend.app.access.service.entitlement_service import entitlement_service
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='获取权益详情', dependencies=[DependsJwtAuth])
async def get_entitlement(
    db: CurrentSession,
    pk: Annotated[int, Path(description='权益 ID')],
) -> ResponseSchemaModel[GetEntitlementDetail]:
    """获取权益详情"""
    data = await entitlement_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get(
    '',
    summary='分页获取权益',
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def get_entitlement_list(
    db: CurrentSession,
    keyword: Annotated[str | None, Query(description='关键字')] = None,
    category: Annotated[EntitlementCategory | None, Query(description='分类')] = None,
    verb: Annotated[EntitlementVerb | None, Query(description='动作')] = None,
    domain_id: Annotated[int | None, Query(description='领域 ID')] = None,
    resource_type: Annotated[str | None, Query(description='资源类型')] = None,
    status: Annotated[CommonStatus | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[PageData[GetEntitlementDetail]]:
    """分页获取权益"""
    stmt = await entitlement_service.get_select(
        keyword=keyword,
        category=category,
        verb=verb,
        domain_id=domain_id,
        resource_type=resource_type,
        status=status,
    )
    page_data = await paging_data(db, stmt)
    return response_base.success(data=page_data)


@router.post(
    '',
    summary='创建权益',
    dependencies=[
        Depends(RequestPermission('access:entitlement:create')),
        DependsRBAC,
    ],
)
async def create_entitlement(db: CurrentSessionTransaction, obj: CreateEntitlementParam) -> ResponseModel:
    """创建权益"""
    await entitlement_service.create(db=db, obj=obj)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新权益',
    dependencies=[
        Depends(RequestPermission('access:entitlement:update')),
        DependsRBAC,
    ],
)
async def update_entitlement(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='权益 ID')],
    obj: UpdateEntitlementParam,
) -> ResponseModel:
    """更新权益"""
    count = await entitlement_service.update(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '/{pk}',
    summary='删除权益',
    dependencies=[
        Depends(RequestPermission('access:entitlement:delete')),
        DependsRBAC,
    ],
)
async def delete_entitlement(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='权益 ID')],
) -> ResponseModel:
    """删除权益"""
    count = await entitlement_service.delete(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
