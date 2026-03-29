#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.app.membership.schema.entitlement import (
    CreateMembershipEntitlementParam,
    GetMembershipEntitlementDetail,
    GetTierEntitlementBrief,
    SetTierEntitlementsParam,
    UpdateMembershipEntitlementParam,
)
from backend.app.membership.service.entitlement_service import membership_entitlement_service
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get(
    '',
    summary='分页查询会员权益',
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def get_entitlement_pagination(
    db: CurrentSession,
    name: Annotated[str | None, Query(description='权益名称')] = None,
    status: Annotated[int | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[PageData[GetMembershipEntitlementDetail]]:
    """分页查询会员权益"""
    entitlement_select = await membership_entitlement_service.get_select(name=name, status=status)
    page_data = await paging_data(db, entitlement_select, GetMembershipEntitlementDetail)
    return response_base.success(data=page_data)


@router.get(
    '/{pk}',
    summary='获取会员权益详情',
    dependencies=[DependsJwtAuth],
)
async def get_entitlement_detail(
    db: CurrentSession,
    pk: Annotated[int, Path(description='权益 ID')],
) -> ResponseSchemaModel[GetMembershipEntitlementDetail]:
    """获取会员权益详情"""
    entitlement = await membership_entitlement_service.get(db, pk=pk)
    return response_base.success(data=GetMembershipEntitlementDetail.model_validate(entitlement))


@router.post(
    '',
    summary='创建会员权益',
    dependencies=[
        Depends(RequestPermission('membership:entitlement:add')),
        DependsRBAC,
    ],
)
async def create_entitlement(
    db: CurrentSessionTransaction,
    obj: CreateMembershipEntitlementParam,
) -> ResponseModel:
    """创建会员权益"""
    await membership_entitlement_service.create(db, obj=obj)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新会员权益',
    dependencies=[
        Depends(RequestPermission('membership:entitlement:edit')),
        DependsRBAC,
    ],
)
async def update_entitlement(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='权益 ID')],
    obj: UpdateMembershipEntitlementParam,
) -> ResponseModel:
    """更新会员权益"""
    await membership_entitlement_service.update(db, pk=pk, obj=obj)
    return response_base.success()


@router.delete(
    '/{pk}',
    summary='删除会员权益',
    dependencies=[
        Depends(RequestPermission('membership:entitlement:del')),
        DependsRBAC,
    ],
)
async def delete_entitlement(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='权益 ID')],
) -> ResponseModel:
    """删除会员权益"""
    await membership_entitlement_service.delete(db, pk=pk)
    return response_base.success()


@router.get(
    '/tiers/{tier_id}',
    summary='查询等级权益映射',
    dependencies=[DependsJwtAuth],
)
async def get_tier_entitlements(
    db: CurrentSession,
    tier_id: Annotated[int, Path(description='等级 ID')],
) -> ResponseSchemaModel[list[GetTierEntitlementBrief]]:
    """查询等级权益映射"""
    rows = await membership_entitlement_service.get_tier_entitlements(db, tier_id=tier_id)
    data = [GetTierEntitlementBrief.model_validate(item) for item in rows]
    return response_base.success(data=data)


@router.put(
    '/tiers/{tier_id}',
    summary='设置等级权益映射',
    dependencies=[
        Depends(RequestPermission('membership:entitlement:bind')),
        DependsRBAC,
    ],
)
async def set_tier_entitlements(
    db: CurrentSessionTransaction,
    tier_id: Annotated[int, Path(description='等级 ID')],
    obj: SetTierEntitlementsParam,
) -> ResponseModel:
    """设置等级权益映射"""
    await membership_entitlement_service.set_tier_entitlements(db, tier_id=tier_id, obj=obj)
    return response_base.success()
