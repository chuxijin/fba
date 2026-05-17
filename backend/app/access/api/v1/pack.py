#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.app.access.constants import CommonStatus, GradeLevel
from backend.app.access.schema.pack import (
    CreatePackParam,
    GetPackDetail,
    SetPackItemsParam,
    UpdatePackParam,
)
from backend.app.access.service.pack_service import entitlement_pack_service
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='获取权益包详情', dependencies=[DependsJwtAuth])
async def get_pack(
    db: CurrentSession,
    pk: Annotated[int, Path(description='包 ID')],
) -> ResponseSchemaModel[GetPackDetail]:
    """获取权益包详情"""
    data = await entitlement_pack_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get(
    '',
    summary='分页获取权益包',
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def get_pack_list(
    db: CurrentSession,
    grade: Annotated[GradeLevel | None, Query(description='档次')] = None,
    domain_id: Annotated[int | None, Query(description='领域 ID')] = None,
    status: Annotated[CommonStatus | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[PageData[GetPackDetail]]:
    """分页获取权益包"""
    stmt = await entitlement_pack_service.get_select(
        grade=grade, domain_id=domain_id, status=status
    )
    page_data = await paging_data(db, stmt)
    return response_base.success(data=page_data)


@router.post(
    '',
    summary='创建权益包',
    dependencies=[
        Depends(RequestPermission('access:pack:create')),
        DependsRBAC,
    ],
)
async def create_pack(
    db: CurrentSessionTransaction, obj: CreatePackParam
) -> ResponseModel:
    """创建权益包"""
    await entitlement_pack_service.create(db=db, obj=obj)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新权益包',
    dependencies=[
        Depends(RequestPermission('access:pack:update')),
        DependsRBAC,
    ],
)
async def update_pack(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='包 ID')],
    obj: UpdatePackParam,
) -> ResponseModel:
    """更新权益包"""
    count = await entitlement_pack_service.update(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '/{pk}',
    summary='删除权益包',
    dependencies=[
        Depends(RequestPermission('access:pack:delete')),
        DependsRBAC,
    ],
)
async def delete_pack(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='包 ID')],
) -> ResponseModel:
    """删除权益包"""
    count = await entitlement_pack_service.delete(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.put(
    '/{pk}/items',
    summary='批量设置权益包成员',
    dependencies=[
        Depends(RequestPermission('access:pack:update')),
        DependsRBAC,
    ],
)
async def set_pack_items(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='包 ID')],
    obj: SetPackItemsParam,
) -> ResponseModel:
    """批量设置权益包成员"""
    await entitlement_pack_service.set_items(db=db, pack_id=pk, obj=obj)
    return response_base.success()
