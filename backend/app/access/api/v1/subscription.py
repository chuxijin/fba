#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query

from backend.app.access.constants import SubscriptionSource, SubscriptionStatus
from backend.app.access.schema.subscription import (
    CancelSubscriptionParam,
    CreateSubscriptionParam,
    GetSubscriptionDetail,
)
from backend.app.access.service.subscription_service import subscription_service
from backend.common.pagination import DependsPagination, PageData, paging_data
from backend.common.response.response_schema import ResponseModel, ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.common.security.permission import RequestPermission
from backend.common.security.rbac import DependsRBAC
from backend.database.db import CurrentSession, CurrentSessionTransaction

router = APIRouter()


@router.get('/{pk}', summary='获取订阅详情', dependencies=[DependsJwtAuth, DependsRBAC])
async def get_subscription(
    db: CurrentSession,
    pk: Annotated[int, Path(description='订阅 ID')],
) -> ResponseSchemaModel[GetSubscriptionDetail]:
    """获取订阅详情"""
    data = await subscription_service.get(db=db, pk=pk)
    return response_base.success(data=data)


@router.get(
    '',
    summary='分页查询用户订阅',
    dependencies=[
        DependsJwtAuth,
        Depends(RequestPermission('access:subscription:query')),
        DependsRBAC,
        DependsPagination,
    ],
)
async def get_subscription_list(
    db: CurrentSession,
    user_id: Annotated[int | None, Query(description='用户 ID')] = None,
    status: Annotated[SubscriptionStatus | None, Query(description='状态')] = None,
    source: Annotated[SubscriptionSource | None, Query(description='来源')] = None,
) -> ResponseSchemaModel[PageData[GetSubscriptionDetail]]:
    """分页查询用户订阅"""
    from backend.app.access.crud.crud_subscription import subscription_dao

    stmt = await subscription_dao.get_select(user_id=user_id, status=status, source=source)
    page_data = await paging_data(db, stmt)
    return response_base.success(data=page_data)


@router.post(
    '',
    summary='管理端创建订阅',
    dependencies=[
        Depends(RequestPermission('access:subscription:create')),
        DependsRBAC,
    ],
)
async def create_subscription(
    db: CurrentSessionTransaction, obj: CreateSubscriptionParam
) -> ResponseModel:
    """管理端创建订阅"""
    await subscription_service.create(db=db, obj=obj)
    return response_base.success()


@router.put(
    '/{pk}/cancel',
    summary='取消订阅',
    dependencies=[
        Depends(RequestPermission('access:subscription:update')),
        DependsRBAC,
    ],
)
async def cancel_subscription(
    db: CurrentSessionTransaction,
    pk: Annotated[int, Path(description='订阅 ID')],
    obj: CancelSubscriptionParam,
) -> ResponseModel:
    """取消订阅"""
    count = await subscription_service.cancel(db=db, pk=pk, obj=obj)
    if count > 0:
        return response_base.success()
    return response_base.fail()
