#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.app.access.constants import CommonStatus, TemplateKind
from backend.app.access.schema.template import (
    CreateTemplateParam,
    GetTemplateDetail,
    GetTemplateDetailWithPacks,
    SetTemplatePacksParam,
    UpdateTemplateParam,
)
from backend.app.access.service.template_service import subscription_template_service
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='获取订阅模板详情', dependencies=[DependsJwtAuth])
async def get_template(
    db: CurrentSession,
    pk: Annotated[int, Path(description='模板 ID')],
) -> ResponseSchemaModel[GetTemplateDetailWithPacks]:
    """获取订阅模板详情"""
    data = await subscription_template_service.get_detail(db=db, pk=pk)
    return response_base.success(data=data)


@router.get(
    '',
    summary='分页获取订阅模板',
    dependencies=[DependsJwtAuth, DependsPagination],
)
async def get_template_list(
    db: CurrentSession,
    kind: Annotated[TemplateKind | None, Query(description='模板类型')] = None,
    status: Annotated[CommonStatus | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[PageData[GetTemplateDetail]]:
    """分页获取订阅模板"""
    stmt = await subscription_template_service.get_select(kind=kind, status=status)
    page_data = await paging_data(db, stmt)
    return response_base.success(data=page_data)


@router.post(
    '',
    summary='创建订阅模板',
    dependencies=[
        Depends(RequestPermission('access:template:create')),
        DependsRBAC,
    ],
)
async def create_template(
    db: CurrentSessionTransaction, obj: CreateTemplateParam
) -> ResponseModel:
    """创建订阅模板"""
    await subscription_template_service.create(db=db, obj=obj)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新订阅模板',
    dependencies=[
        Depends(RequestPermission('access:template:update')),
        DependsRBAC,
    ],
)
async def update_template(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='模板 ID')],
    obj: UpdateTemplateParam,
) -> ResponseModel:
    """更新订阅模板"""
    count = await subscription_template_service.update(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '/{pk}',
    summary='删除订阅模板',
    dependencies=[
        Depends(RequestPermission('access:template:delete')),
        DependsRBAC,
    ],
)
async def delete_template(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='模板 ID')],
) -> ResponseModel:
    """删除订阅模板"""
    count = await subscription_template_service.delete(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.put(
    '/{pk}/packs',
    summary='设置模板关联的权益包',
    dependencies=[
        Depends(RequestPermission('access:template:update')),
        DependsRBAC,
    ],
)
async def set_template_packs(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='模板 ID')],
    obj: SetTemplatePacksParam,
) -> ResponseModel:
    """设置模板关联的权益包"""
    await subscription_template_service.set_packs(db=db, template_id=pk, obj=obj)
    return response_base.success()
