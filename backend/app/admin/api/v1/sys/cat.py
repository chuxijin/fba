#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.admin.schema.cat import (
    BatchBindCatsParam,
    CreateSysCatParam,
    CreateSysCatTargetParam,
    GetSysCatTargetWithCat,
    GetSysCatTree,
    UpdateSysCatParam,
)
from backend.app.admin.service.cat_service import sys_cat_service, sys_cat_target_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(dependencies=[DependsJwtAuth])


# ==================== 分类 CRUD ====================


@router.get(
    '/tree',
    summary='获取分类树',
    response_model=ResponseSchemaModel[list[GetSysCatTree]],
)
async def get_sys_cat_tree(
    db: CurrentSession,
    app_code: Annotated[str | None, Query(description='应用标识')] = None,
    user_id: Annotated[int | None, Query(description='用户 ID')] = None,
    status: Annotated[bool | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[list[GetSysCatTree]]:
    data = await sys_cat_service.get_tree(db=db, app_code=app_code, user_id=user_id, status=status)
    return response_base.success(data=data)


@router.post(
    '',
    summary='创建分类',
    response_model=ResponseSchemaModel[GetSysCatTree],
)
async def create_sys_cat(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateSysCatParam,
) -> ResponseSchemaModel[GetSysCatTree]:
    data = await sys_cat_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success(data=data)


@router.put(
    '/{pk}',
    summary='更新分类',
    response_model=ResponseModel,
)
async def update_sys_cat(
    request: Request,
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='分类 ID')],
    obj: UpdateSysCatParam,
) -> ResponseModel:
    count = await sys_cat_service.update(db=db, pk=pk, obj=obj, updated_by=request.user.id)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '/{pk}',
    summary='删除分类',
    response_model=ResponseModel,
)
async def delete_sys_cat(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='分类 ID')],
) -> ResponseModel:
    count = await sys_cat_service.delete(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()


# ==================== 分类关联 CRUD ====================


@router.get(
    '/targets',
    summary='获取目标的分类列表',
    response_model=ResponseSchemaModel[list[GetSysCatTargetWithCat]],
)
async def get_sys_cat_targets(
    db: CurrentSession,
    target_type: Annotated[str, Query(description='目标类型')],
    target_id: Annotated[int, Query(description='目标 ID')],
) -> ResponseSchemaModel[list[GetSysCatTargetWithCat]]:
    data = await sys_cat_target_service.get_targets(db=db, target_type=target_type, target_id=target_id)
    return response_base.success(data=data)


@router.post(
    '/bind',
    summary='绑定分类到目标',
    response_model=ResponseModel,
)
async def bind_sys_cat(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateSysCatTargetParam,
) -> ResponseModel:
    await sys_cat_target_service.bind(db=db, obj=obj, created_by=request.user.id)
    return response_base.success()


@router.post(
    '/batch-bind',
    summary='批量绑定分类到目标',
    response_model=ResponseModel,
)
async def batch_bind_sys_cats(
    request: Request,
    db: CurrentSessionTransaction,
    obj: BatchBindCatsParam,
) -> ResponseModel:
    await sys_cat_target_service.batch_bind(db=db, obj=obj, created_by=request.user.id)
    return response_base.success()


@router.delete(
    '/unbind/{pk}',
    summary='解绑分类关联',
    response_model=ResponseModel,
)
async def unbind_sys_cat(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='关联 ID')],
) -> ResponseModel:
    count = await sys_cat_target_service.unbind(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
