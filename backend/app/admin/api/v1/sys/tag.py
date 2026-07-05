#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Path, Query, Request

from backend.app.admin.schema.tag import (
    BatchBindTagsParam,
    CreateSysTagParam,
    CreateSysTagTargetParam,
    GetSysTagListItem,
    GetSysTagTargetWithTag,
    UpdateSysTagParam,
)
from backend.app.admin.service.tag_service import sys_tag_service, sys_tag_target_service
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter(dependencies=[DependsJwtAuth])


# ==================== 标签 CRUD ====================


@router.get(
    '',
    summary='获取标签列表',
    response_model=ResponseSchemaModel[list[GetSysTagListItem]],
)
async def get_sys_tags(
    db: CurrentSession,
    app_code: Annotated[str | None, Query(description='应用标识')] = None,
    user_id: Annotated[int | None, Query(description='用户 ID')] = None,
    name: Annotated[str | None, Query(description='标签名称')] = None,
    status: Annotated[bool | None, Query(description='状态')] = None,
) -> ResponseSchemaModel[list[GetSysTagListItem]]:
    data = await sys_tag_service.get_list(
        db=db,
        app_code=app_code,
        user_id=user_id,
        name=name,
        status=status,
    )
    return response_base.success(data=data)


@router.post(
    '',
    summary='创建标签',
    response_model=ResponseSchemaModel[GetSysTagListItem],
)
async def create_sys_tag(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateSysTagParam,
) -> ResponseSchemaModel[GetSysTagListItem]:
    data = await sys_tag_service.create(db=db, obj=obj, created_by=request.user.id)
    return response_base.success(data=data)


@router.put(
    '/{pk}',
    summary='更新标签',
    response_model=ResponseModel,
)
async def update_sys_tag(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='标签 ID')],
    obj: UpdateSysTagParam,
) -> ResponseModel:
    count = await sys_tag_service.update(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '/{pk}',
    summary='删除标签',
    response_model=ResponseModel,
)
async def delete_sys_tag(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='标签 ID')],
) -> ResponseModel:
    count = await sys_tag_service.delete(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()


# ==================== 标签关联 CRUD ====================


@router.get(
    '/targets',
    summary='获取目标的标签列表',
    response_model=ResponseSchemaModel[list[GetSysTagTargetWithTag]],
)
async def get_sys_tag_targets(
    db: CurrentSession,
    target_type: Annotated[str, Query(description='目标类型')],
    target_id: Annotated[int, Query(description='目标 ID')],
) -> ResponseSchemaModel[list[GetSysTagTargetWithTag]]:
    data = await sys_tag_target_service.get_targets(
        db=db,
        target_type=target_type,
        target_id=target_id,
    )
    return response_base.success(data=data)


@router.post(
    '/bind',
    summary='绑定标签到目标',
    response_model=ResponseModel,
)
async def bind_sys_tag(
    request: Request,
    db: CurrentSessionTransaction,
    obj: CreateSysTagTargetParam,
) -> ResponseModel:
    await sys_tag_target_service.bind(db=db, obj=obj, created_by=request.user.id)
    return response_base.success()


@router.post(
    '/batch-bind',
    summary='批量绑定标签到目标',
    response_model=ResponseModel,
)
async def batch_bind_sys_tags(
    request: Request,
    db: CurrentSessionTransaction,
    obj: BatchBindTagsParam,
) -> ResponseModel:
    await sys_tag_target_service.batch_bind(db=db, obj=obj, created_by=request.user.id)
    return response_base.success()


@router.delete(
    '/unbind/{pk}',
    summary='解绑标签关联',
    response_model=ResponseModel,
)
async def unbind_sys_tag(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='关联 ID')],
) -> ResponseModel:
    count = await sys_tag_target_service.unbind(db=db, pk=pk)
    if count > 0:
        return response_base.success()
    return response_base.fail()
