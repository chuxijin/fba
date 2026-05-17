#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.app.access.schema.domain import (
    CreateStudyDomainParam,
    GetStudyDomainDetail,
    UpdateStudyDomainParam,
)
from backend.app.access.service.domain_service import study_domain_service
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='获取学习领域详情', dependencies=[DependsJwtAuth])
async def get_study_domain(
    db: CurrentSession,
    pk: Annotated[int, Path(description='领域 ID')],
) -> ResponseSchemaModel[GetStudyDomainDetail]:
    """获取学习领域详情"""
    data = await study_domain_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get(
    '',
    summary='分页获取学习领域',
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def get_study_domain_list(
    db: CurrentSession,
    keyword: Annotated[str | None, Query(description='关键字')] = None,
) -> ResponseSchemaModel[PageData[GetStudyDomainDetail]]:
    """分页获取学习领域"""
    stmt = await study_domain_service.get_select(keyword=keyword)
    page_data = await paging_data(db, stmt)
    return response_base.success(data=page_data)


@router.post(
    '',
    summary='创建学习领域',
    dependencies=[
        Depends(RequestPermission('access:domain:create')),
        DependsRBAC,
    ],
)
async def create_study_domain(
    db: CurrentSessionTransaction, obj: CreateStudyDomainParam
) -> ResponseModel:
    """创建学习领域"""
    await study_domain_service.create(db=db, obj=obj)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新学习领域',
    dependencies=[
        Depends(RequestPermission('access:domain:update')),
        DependsRBAC,
    ],
)
async def update_study_domain(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='领域 ID')],
    obj: UpdateStudyDomainParam,
) -> ResponseModel:
    """更新学习领域"""
    count = await study_domain_service.update(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '/{pk}',
    summary='删除学习领域',
    dependencies=[
        Depends(RequestPermission('access:domain:delete')),
        DependsRBAC,
    ],
)
async def delete_study_domain(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='领域 ID')],
) -> ResponseModel:
    """删除学习领域"""
    count = await study_domain_service.delete(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
