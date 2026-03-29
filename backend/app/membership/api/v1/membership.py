#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from backend.app.membership.schema.membership import (
    AddDaysParam,
    AddExperienceParam,
    GetUserMembershipBrief,
    OpenMembershipParam,
)
from backend.app.membership.schema.plan import GetMembershipPlanBrief
from backend.app.membership.schema.record import GetMembershipRecordBrief
from backend.app.membership.service.experience_service import membership_experience_service
from backend.app.membership.service.membership_service import membership_service
from backend.app.membership.service.plan_service import membership_plan_service
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get(
    '/plans/available',
    summary='获取可购买会员计划',
    dependencies=[DependsJwtAuth],
)
async def get_available_plans(
    db: CurrentSession,
) -> ResponseSchemaModel[list[GetMembershipPlanBrief]]:
    """获取所有上架会员计划"""
    plans = await membership_plan_service.get_active_plans(db)
    data = [GetMembershipPlanBrief.model_validate(plan) for plan in plans]
    return response_base.success(data=data)


@router.get(
    '/me',
    summary='查询当前用户会员信息',
    dependencies=[DependsJwtAuth],
)
async def get_my_membership(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[list[GetUserMembershipBrief]]:
    """查询当前用户的生效会员"""
    memberships = await membership_service.get_user_membership_info(db, user_id=request.user.id)
    data = [GetUserMembershipBrief.model_validate(m) for m in memberships]
    return response_base.success(data=data)


@router.get(
    '/me/progress',
    summary='查询当前用户会员经验进度',
    dependencies=[DependsJwtAuth],
)
async def get_my_membership_progress(
    request: Request,
    db: CurrentSession,
    family_code: Annotated[str | None, Query(description='等级族群')] = None,
) -> ResponseSchemaModel[list[dict[str, int | str | None]]]:
    """查询当前用户会员经验进度"""
    data = await membership_experience_service.get_user_progress(
        db,
        user_id=request.user.id,
        family_code=family_code,
    )
    return response_base.success(data=data)


@router.get(
    '/me/records',
    summary='查询当前用户会员流水',
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def get_my_records(
    request: Request,
    db: CurrentSession,
    family_code: Annotated[str | None, Query(description='等级族群')] = None,
    plan_id: Annotated[int | None, Query(description='会员计划 ID')] = None,
    tier_id: Annotated[int | None, Query(description='会员等级 ID')] = None,
) -> ResponseSchemaModel[PageData[GetMembershipRecordBrief]]:
    """查询当前用户会员变动记录"""
    record_select = await membership_service.get_user_records(
        db,
        user_id=request.user.id,
        family_code=family_code,
        plan_id=plan_id,
        tier_id=tier_id,
    )
    page_data = await paging_data(db, record_select, GetMembershipRecordBrief)
    return response_base.success(data=page_data)


@router.post(
    '/open',
    summary='为用户开通会员',
    dependencies=[
        Depends(RequestPermission('membership:user:open')),
        DependsRBAC,
    ],
)
async def open_membership(
    db: CurrentSessionTransaction,
    obj: OpenMembershipParam,
) -> ResponseModel:
    """管理员为用户开通会员"""
    await membership_service.open_membership(db, obj=obj)
    return response_base.success()


@router.post(
    '/add-days',
    summary='为用户增加会员天数',
    dependencies=[
        Depends(RequestPermission('membership:user:add-days')),
        DependsRBAC,
    ],
)
async def add_membership_days(
    db: CurrentSessionTransaction,
    obj: AddDaysParam,
) -> ResponseModel:
    """管理员为用户增加会员天数"""
    await membership_service.add_days(
        db,
        user_id=obj.user_id,
        plan_id=obj.plan_id,
        days=obj.days,
        source=obj.source,
        source_key=obj.source_key,
        source_detail=obj.source_detail,
        remark=obj.remark,
    )
    return response_base.success()


@router.post(
    '/add-exp',
    summary='为用户增加会员经验',
    dependencies=[
        Depends(RequestPermission('membership:user:add-exp')),
        DependsRBAC,
    ],
)
async def add_membership_experience(
    db: CurrentSessionTransaction,
    obj: AddExperienceParam,
) -> ResponseSchemaModel[dict[str, int | str | None]]:
    """管理员为用户增加会员经验"""
    data = await membership_experience_service.add_experience(
        db,
        user_id=obj.user_id,
        family_code=obj.family_code,
        exp_delta=obj.exp_delta,
        source=obj.source,
        source_key=obj.source_key,
        remark=obj.remark,
    )
    return response_base.success(data=data)
