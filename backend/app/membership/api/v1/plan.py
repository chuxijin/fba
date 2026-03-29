#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.app.membership.schema.plan import (
    CreateMembershipPlanParam,
    GetMembershipPlanDetail,
    UpdateMembershipPlanParam,
)
from backend.app.membership.service.plan_service import membership_plan_service
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get(
    '',
    summary='分页查询会员计划',
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def get_plan_pagination(
    db: CurrentSession,
    name: Annotated[str | None, Query(description='计划名称')] = None,
    status: Annotated[int | None, Query(description='状态')] = None,
    tier_id: Annotated[int | None, Query(description='会员等级 ID')] = None,
) -> ResponseSchemaModel[PageData[GetMembershipPlanDetail]]:
    """分页查询会员计划"""
    plan_select = await membership_plan_service.get_select(name=name, status=status, tier_id=tier_id)
    page_data = await paging_data(db, plan_select, GetMembershipPlanDetail)
    return response_base.success(data=page_data)


@router.get(
    '/{pk}',
    summary='获取会员计划详情',
    dependencies=[DependsJwtAuth],
)
async def get_plan_detail(
    db: CurrentSession,
    pk: Annotated[int, Path(description='计划 ID')],
) -> ResponseSchemaModel[GetMembershipPlanDetail]:
    """获取会员计划详情"""
    plan = await membership_plan_service.get(db, pk=pk)
    return response_base.success(data=GetMembershipPlanDetail.model_validate(plan))


@router.post(
    '',
    summary='创建会员计划',
    dependencies=[
        Depends(RequestPermission('membership:plan:add')),
        DependsRBAC,
    ],
)
async def create_plan(
    db: CurrentSessionTransaction,
    obj: CreateMembershipPlanParam,
) -> ResponseModel:
    """创建会员计划"""
    await membership_plan_service.create(db, obj=obj)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新会员计划',
    dependencies=[
        Depends(RequestPermission('membership:plan:edit')),
        DependsRBAC,
    ],
)
async def update_plan(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='计划 ID')],
    obj: UpdateMembershipPlanParam,
) -> ResponseModel:
    """更新会员计划"""
    await membership_plan_service.update(db, pk=pk, obj=obj)
    return response_base.success()


@router.delete(
    '/{pk}',
    summary='删除会员计划',
    dependencies=[
        Depends(RequestPermission('membership:plan:del')),
        DependsRBAC,
    ],
)
async def delete_plan(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='计划 ID')],
) -> ResponseModel:
    """删除会员计划"""
    await membership_plan_service.delete(db, pk=pk)
    return response_base.success()
