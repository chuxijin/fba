#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.app.growth.crud.crud_experience_rule import experience_rule_dao
from backend.app.growth.schema.experience_rule import (
    CreateExperienceRuleParam,
    GetExperienceRuleDetail,
    UpdateExperienceRuleParam,
)
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='获取经验规则详情', dependencies=[DependsJwtAuth])
async def get_experience_rule(
    db: CurrentSession,
    pk: Annotated[int, Path(description='规则 ID')],
) -> ResponseSchemaModel[GetExperienceRuleDetail]:
    """获取经验规则详情"""
    from backend.common.exception import errors

    rule = await experience_rule_dao.select_model(db, pk)
    if not rule:
        raise errors.NotFoundError(msg='经验规则不存在')
    return response_base.success(data=rule)


@router.get(
    '',
    summary='分页获取经验规则',
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def get_experience_rule_list(
    db: CurrentSession,
    event_code: Annotated[str | None, Query(description='事件编码')] = None,
    family_code: Annotated[str | None, Query(description='族群')] = None,
    status: Annotated[int | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[PageData[GetExperienceRuleDetail]]:
    """分页获取经验规则"""
    stmt = await experience_rule_dao.get_select(
        event_code=event_code, family_code=family_code, status=status
    )
    page_data = await paging_data(db, stmt)
    return response_base.success(data=page_data)


@router.post(
    '',
    summary='创建经验规则',
    dependencies=[
        Depends(RequestPermission('growth:rule:create')),
        DependsRBAC,
    ],
)
async def create_experience_rule(
    db: CurrentSessionTransaction, obj: CreateExperienceRuleParam
) -> ResponseModel:
    """创建经验规则"""
    await experience_rule_dao.create_model(db, obj)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新经验规则',
    dependencies=[
        Depends(RequestPermission('growth:rule:update')),
        DependsRBAC,
    ],
)
async def update_experience_rule(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='规则 ID')],
    obj: UpdateExperienceRuleParam,
) -> ResponseModel:
    """更新经验规则"""
    count = await experience_rule_dao.update_model(db, pk, obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '/{pk}',
    summary='删除经验规则',
    dependencies=[
        Depends(RequestPermission('growth:rule:delete')),
        DependsRBAC,
    ],
)
async def delete_experience_rule(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='规则 ID')],
) -> ResponseModel:
    """删除经验规则"""
    count = await experience_rule_dao.delete_model(db, pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
