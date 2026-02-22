#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Request

from backend.app.gongkao.schema.jingyan import (
    CreateJingyanParam,
    DeleteJingyanParam,
    GetJingyanDetail,
    JingyanParam,
    UpdateJingyanParam,
)
from backend.app.gongkao.service.jingyan_service import jingyan_service
from backend.common.pagination import DependsPagination, PageData
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='获取经验详情')
async def get_jingyan(
    db: CurrentSession,
    pk: Annotated[int, Path(description='经验 ID')],
) -> ResponseSchemaModel[GetJingyanDetail]:
    """获取经验详情"""
    data = await jingyan_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get(
    '',
    summary='获取经验列表',
    dependencies=[DependsPagination],
)
async def get_jingyan_list(
    db: CurrentSession,
    title: Annotated[str | None, Query(description='标题')] = None,
    category_id: Annotated[int | None, Query(description='分类 ID')] = None,
    author: Annotated[str | None, Query(description='作者')] = None,
    tags: Annotated[str | None, Query(description='标签')] = None,
) -> ResponseSchemaModel[PageData[GetJingyanDetail]]:
    """获取经验列表（分页）"""
    params = JingyanParam(
        title=title,
        category_id=category_id,
        author=author,
        tags=tags,
    )
    data = await jingyan_service.get_list(db=db, params=params)
    return response_base.success(data=data)


@router.post(
    '',
    summary='创建经验',
    dependencies=[
        Depends(RequestPermission('gongkao:jingyan:create')),
        DependsRBAC,
    ],
)
async def create_jingyan(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateJingyanParam,
) -> ResponseModel:
    """创建经验"""
    await jingyan_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success()


@router.put(
    '/{pk}',
    summary='更新经验',
    dependencies=[
        Depends(RequestPermission('gongkao:jingyan:update')),
        DependsRBAC,
    ],
)
async def update_jingyan(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='经验 ID')],
    obj: UpdateJingyanParam,
) -> ResponseModel:
    """更新经验"""
    count = await jingyan_service.update(db=db, pk=pk, obj=obj, updated_by=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '',
    summary='删除经验',
    dependencies=[
        Depends(RequestPermission('gongkao:jingyan:delete')),
        DependsRBAC,
    ],
)
async def delete_jingyan(db: CurrentSessionTransaction, obj: DeleteJingyanParam) -> ResponseModel:
    """删除经验"""
    count = await jingyan_service.delete(db=db, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.post('/{pk}/view', summary='增加经验阅读量')
async def increment_jingyan_view(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='经验 ID')],
) -> ResponseModel:
    """增加经验阅读量"""
    count = await jingyan_service.increment_view(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
