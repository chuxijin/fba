#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.common.exception import errors
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession
from backend.plugin.webhook.crud.crud_event_type import crud_event_type
from backend.plugin.webhook.schema.event_type import (
    CreateEventTypeParam,
    EventTypeListParam,
    GetEventTypeDetail,
    UpdateEventTypeParam,
)

router = APIRouter()


@router.post(
    '',
    summary='注册事件类型',
    dependencies=[
        Depends(RequestPermission('sys:webhook_event_type:add')),
        DependsRBAC,
    ],
)
async def register_event_type(obj: CreateEventTypeParam) -> ResponseSchemaModel[GetEventTypeDetail]:
    """注册新的事件类型"""
    from backend.database.db import async_db_session

    async with async_db_session.begin() as db:
        existing = await crud_event_type.get_by_type_key(db, obj.type_key)
        if existing:
            raise errors.ConflictError(msg=f'事件类型 {obj.type_key} 已存在')
        event_type = await crud_event_type.create(db, obj)
        await db.flush()
        await db.refresh(event_type)
        return response_base.success(data=GetEventTypeDetail.model_validate(event_type))


@router.get(
    '',
    summary='分页获取事件类型列表',
    dependencies=[
        DependsJwtAuth,
        DependsPagination,
    ],
)
async def list_event_types(
    db: CurrentSession,
    category: Annotated[str | None, Query(description='分类')] = None,
    is_active: Annotated[bool | None, Query(description='是否启用')] = None,
) -> ResponseSchemaModel[PageData[GetEventTypeDetail]]:
    """分页获取事件类型列表"""
    params = EventTypeListParam(category=category, is_active=is_active)
    select = await crud_event_type.get_list(params)
    page_data = await paging_data(db, select)
    return response_base.success(data=page_data)


@router.get('/{pk}', summary='获取事件类型详情', dependencies=[DependsJwtAuth])
async def get_event_type(
    pk: Annotated[int, Path(description='事件类型 ID')],
) -> ResponseSchemaModel[GetEventTypeDetail]:
    """获取事件类型详情"""
    from backend.database.db import async_db_session

    async with async_db_session() as db:
        event_type = await crud_event_type.get(db, pk)
    if not event_type:
        raise errors.NotFoundError(msg='事件类型不存在')
    return response_base.success(data=GetEventTypeDetail.model_validate(event_type))


@router.put(
    '/{pk}',
    summary='更新事件类型',
    dependencies=[
        Depends(RequestPermission('sys:webhook_event_type:edit')),
        DependsRBAC,
    ],
)
async def update_event_type(
    pk: Annotated[int, Path(description='事件类型 ID')],
    obj: UpdateEventTypeParam,
) -> ResponseModel:
    """更新事件类型"""
    from backend.database.db import async_db_session

    async with async_db_session.begin() as db:
        count = await crud_event_type.update(db, pk, obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()


@router.delete(
    '',
    summary='批量删除事件类型',
    dependencies=[
        Depends(RequestPermission('sys:webhook_event_type:del')),
        DependsRBAC,
    ],
)
async def delete_event_types(pks: list[int]) -> ResponseModel:
    """批量删除事件类型"""
    from backend.database.db import async_db_session

    async with async_db_session.begin() as db:
        count = await crud_event_type.delete(db, pks)
    if count > 0:
        return response_base.success()
    return response_base.fail()
