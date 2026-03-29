#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.app.membership.schema.tier import (
    CreateMembershipTierParam,
    GetMembershipTierBrief,
    GetMembershipTierDetail,
    UpdateMembershipTierParam,
)
from backend.app.membership.service.tier_service import membership_tier_service
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get(
    '/active',
    summary='获取启用会员等级',
    dependencies=[DependsJwtAuth],
)
async def get_active_tiers(
    db: CurrentSession,
) -> ResponseSchemaModel[list[GetMembershipTierBrief]]:
    """获取启用会员等级列表"""
    tiers = await membership_tier_service.get_active_tiers(db)
    data = [GetMembershipTierBrief.model_validate(tier) for tier in tiers]
    return response_base.success(data=data)


@router.get(
    '',
    summary='分页查询会员等级',
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def get_tier_pagination(
    db: CurrentSession,
    name: Annotated[str | None, Query(description='等级名称')] = None,
    status: Annotated[int | None, Query(description='状态')] = None,
    family_code: Annotated[str | None, Query(description='等级族群')] = None,
) -> ResponseSchemaModel[PageData[GetMembershipTierDetail]]:
    """分页查询会员等级"""
    tier_select = await membership_tier_service.get_select(name=name, status=status, family_code=family_code)
    page_data = await paging_data(db, tier_select, GetMembershipTierDetail)
    return response_base.success(data=page_data)


@router.get(
    '/{pk}',
    summary='获取会员等级详情',
    dependencies=[DependsJwtAuth],
)
async def get_tier_detail(
    db: CurrentSession,
    pk: Annotated[int, Path(description='等级 ID')],
) -> ResponseSchemaModel[GetMembershipTierDetail]:
    """获取会员等级详情"""
    tier = await membership_tier_service.get(db, pk=pk)
    return response_base.success(data=GetMembershipTierDetail.model_validate(tier))


@router.post(
    '',
    summary='创建会员等级',
    dependencies=[
        Depends(RequestPermission('membership:tier:add')),
        DependsRBAC,
    ],
)
async def create_tier(
    db: CurrentSessionTransaction,
    obj: CreateMembershipTierParam,
) -> ResponseModel:
    """创建会员等级"""
    await membership_tier_service.create(db, obj=obj)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新会员等级',
    dependencies=[
        Depends(RequestPermission('membership:tier:edit')),
        DependsRBAC,
    ],
)
async def update_tier(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='等级 ID')],
    obj: UpdateMembershipTierParam,
) -> ResponseModel:
    """更新会员等级"""
    await membership_tier_service.update(db, pk=pk, obj=obj)
    return response_base.success()


@router.delete(
    '/{pk}',
    summary='删除会员等级',
    dependencies=[
        Depends(RequestPermission('membership:tier:del')),
        DependsRBAC,
    ],
)
async def delete_tier(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='等级 ID')],
) -> ResponseModel:
    """删除会员等级"""
    await membership_tier_service.delete(db, pk=pk)
    return response_base.success()
