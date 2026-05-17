#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.app.access.constants import CommonStatus, GrantMode
from backend.app.access.schema.rule import (
    BulkUpsertRulesParam,
    CreateRuleParam,
    GetRuleDetail,
    UpdateRuleParam,
)
from backend.app.access.service.rule_service import resource_rule_service
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='获取资源规则详情', dependencies=[DependsJwtAuth])
async def get_rule(
    db: CurrentSession,
    pk: Annotated[int, Path(description='规则 ID')],
) -> ResponseSchemaModel[GetRuleDetail]:
    """获取资源规则详情"""
    data = await resource_rule_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get(
    '',
    summary='分页查询资源规则',
    dependencies=[
        DependsJwtAuth,
        Depends(RequestPermission('access:rule:query')),
        DependsRBAC,
        DependsPagination,
    ],
)
async def get_rule_list(
    db: CurrentSession,
    resource_type: Annotated[str | None, Query(description='资源类型')] = None,
    resource_id: Annotated[int | None, Query(description='资源 ID')] = None,
    entitlement_code: Annotated[str | None, Query(description='权益编码')] = None,
    grant_mode: Annotated[GrantMode | None, Query(description='授权模式')] = None,
    status: Annotated[CommonStatus | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[PageData[GetRuleDetail]]:
    """分页查询资源规则"""
    stmt = await resource_rule_service.get_select(
        resource_type=resource_type,
        resource_id=resource_id,
        entitlement_code=entitlement_code,
        grant_mode=grant_mode,
        status=status,
    )
    page_data = await paging_data(db, stmt)
    return response_base.success(data=page_data)


@router.post(
    '',
    summary='创建资源规则',
    dependencies=[
        Depends(RequestPermission('access:rule:create')),
        DependsRBAC,
    ],
)
async def create_rule(
    db: CurrentSessionTransaction, obj: CreateRuleParam
) -> ResponseModel:
    """创建资源规则"""
    await resource_rule_service.create(db=db, obj=obj)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新资源规则',
    dependencies=[
        Depends(RequestPermission('access:rule:update')),
        DependsRBAC,
    ],
)
async def update_rule(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='规则 ID')],
    obj: UpdateRuleParam,
) -> ResponseModel:
    """更新资源规则"""
    count = await resource_rule_service.update(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '/{pk}',
    summary='删除资源规则',
    dependencies=[
        Depends(RequestPermission('access:rule:delete')),
        DependsRBAC,
    ],
)
async def delete_rule(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='规则 ID')],
) -> ResponseModel:
    """删除资源规则"""
    count = await resource_rule_service.delete(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.post(
    '/bulk-upsert',
    summary='按资源类型批量回填规则',
    dependencies=[
        Depends(RequestPermission('access:rule:create')),
        DependsRBAC,
    ],
)
async def bulk_upsert_rules(
    db: CurrentSessionTransaction, obj: BulkUpsertRulesParam
) -> ResponseModel:
    """按资源类型批量回填规则"""
    count = await resource_rule_service.bulk_upsert(db=db, obj=obj)
    return response_base.success(data={'created': count})
