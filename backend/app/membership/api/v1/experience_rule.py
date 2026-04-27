#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.app.membership.schema.experience_rule import (
    CreateMembershipExperienceRuleParam,
    GetMembershipExperienceRuleDetail,
    UpdateMembershipExperienceRuleParam,
)
from backend.app.membership.service.experience_rule_service import membership_experience_rule_service
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get(
    '',
    summary='分页查询会员经验规则',
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def get_experience_rule_pagination(
    db: CurrentSession,
    event_code: Annotated[str | None, Query(description='事件编码')] = None,
    family_code: Annotated[str | None, Query(description='等级族群')] = None,
    status: Annotated[int | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[PageData[GetMembershipExperienceRuleDetail]]:
    """分页查询会员经验规则"""
    rule_select = await membership_experience_rule_service.get_select(
        event_code=event_code,
        family_code=family_code,
        status=status,
    )
    page_data = await paging_data(db, rule_select, GetMembershipExperienceRuleDetail)
    return response_base.success(data=page_data)


@router.get(
    '/{pk}',
    summary='获取会员经验规则详情',
    dependencies=[DependsJwtAuth],
)
async def get_experience_rule_detail(
    db: CurrentSession,
    pk: Annotated[int, Path(description='规则 ID')],
) -> ResponseSchemaModel[GetMembershipExperienceRuleDetail]:
    """获取会员经验规则详情"""
    rule = await membership_experience_rule_service.get(db, pk=pk)
    return response_base.success(data=GetMembershipExperienceRuleDetail.model_validate(rule))


@router.post(
    '',
    summary='创建会员经验规则',
    dependencies=[
        Depends(RequestPermission('membership:experience-rule:add')),
        DependsRBAC,
    ],
)
async def create_experience_rule(
    db: CurrentSessionTransaction,
    obj: CreateMembershipExperienceRuleParam,
) -> ResponseModel:
    """创建会员经验规则"""
    await membership_experience_rule_service.create(db, obj=obj)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新会员经验规则',
    dependencies=[
        Depends(RequestPermission('membership:experience-rule:edit')),
        DependsRBAC,
    ],
)
async def update_experience_rule(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='规则 ID')],
    obj: UpdateMembershipExperienceRuleParam,
) -> ResponseModel:
    """更新会员经验规则"""
    await membership_experience_rule_service.update(db, pk=pk, obj=obj)
    return response_base.success()


@router.delete(
    '/{pk}',
    summary='删除会员经验规则',
    dependencies=[
        Depends(RequestPermission('membership:experience-rule:del')),
        DependsRBAC,
    ],
)
async def delete_experience_rule(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='规则 ID')],
) -> ResponseModel:
    """删除会员经验规则"""
    await membership_experience_rule_service.delete(db, pk=pk)
    return response_base.success()
