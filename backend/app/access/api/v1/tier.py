#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.app.access.constants import CommonStatus
from backend.app.access.schema.tier import (
    CreateMembershipTierParam,
    GetMembershipTierDetail,
    UpdateMembershipTierParam,
)
from backend.app.access.service.tier_service import membership_tier_service
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='获取会员档位详情', dependencies=[DependsJwtAuth])
async def get_membership_tier(
    db: CurrentSession,
    pk: Annotated[int, Path(description='会员档位 ID')],
) -> ResponseSchemaModel[GetMembershipTierDetail]:
    data = await membership_tier_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get(
    '',
    summary='分页获取会员档位',
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def get_membership_tiers_paginated(
    db: CurrentSession,
    keyword: Annotated[str | None, Query(description='编码或名称关键字')] = None,
    status: Annotated[CommonStatus | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[PageData[GetMembershipTierDetail]]:
    stmt = await membership_tier_service.get_select(keyword=keyword, status=status)
    return response_base.success(data=await paging_data(db, stmt))


@router.post(
    '',
    summary='创建会员档位',
    dependencies=[Depends(RequestPermission('access:template:create')), DependsRBAC],
)
async def create_membership_tier(
    db: CurrentSessionTransaction,
    obj: CreateMembershipTierParam,
) -> ResponseModel:
    await membership_tier_service.create(db=db, obj=obj)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新会员档位',
    dependencies=[Depends(RequestPermission('access:template:update')), DependsRBAC],
)
async def update_membership_tier(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='会员档位 ID')],
    obj: UpdateMembershipTierParam,
) -> ResponseModel:
    count = await membership_tier_service.update(db=db, pk=pk, obj=obj)
    return response_base.success() if count > 0 else response_base.fail()


@router.delete(
    '/{pk}',
    summary='删除会员档位',
    dependencies=[Depends(RequestPermission('access:template:delete')), DependsRBAC],
)
async def delete_membership_tier(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='会员档位 ID')],
) -> ResponseModel:
    count = await membership_tier_service.delete(db=db, pk=pk)
    return response_base.success() if count > 0 else response_base.fail()
