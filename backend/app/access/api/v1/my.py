#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Query, Request

from backend.app.access.constants import CycleType
from backend.app.access.engine.cycle import build_cycle_key
from backend.app.access.engine.ledger import ledger_service
from backend.app.access.schema.entitlement import GetMyEntitlement
from backend.app.access.schema.ledger import GetQuotaBalance
from backend.app.access.schema.my import GetMyAccessSummary
from backend.app.access.schema.subscription import GetMySubscription, GetMySubscriptionLedger
from backend.app.access.service.my_service import my_access_service
from backend.common.response.response_schema import ResponseSchemaModel, response_base
from backend.common.security.jwt import DependsJwtAuth
from backend.database.db import CurrentSession

router = APIRouter()


@router.get(
    '/subscriptions',
    summary='我的订阅列表',
    dependencies=[DependsJwtAuth],
)
async def get_my_subscriptions(
    request: Request,
    db: CurrentSession,
    only_active: Annotated[bool, Query(description='仅当前有效')] = False,
) -> ResponseSchemaModel[list[GetMySubscription]]:
    """我的订阅列表"""
    user_id = int(request.user.id)
    data = await my_access_service.get_subscriptions(
        db=db, user_id=user_id, only_active=only_active
    )
    return response_base.success(data=data)


@router.get(
    '/entitlements',
    summary='我的权益列表',
    dependencies=[DependsJwtAuth],
)
async def get_my_entitlements(
    request: Request,
    db: CurrentSession,
) -> ResponseSchemaModel[list[GetMyEntitlement]]:
    """我的权益列表"""
    user_id = int(request.user.id)
    data = await my_access_service.get_entitlements(db=db, user_id=user_id)
    return response_base.success(data=data)


@router.get(
    '/summary',
    summary='我的权益汇总',
    dependencies=[DependsJwtAuth],
)
async def get_my_access_summary(
    request: Request,
    db: CurrentSession,
    force_refresh: Annotated[bool, Query(description='强制刷新缓存')] = False,
) -> ResponseSchemaModel[GetMyAccessSummary]:
    """我的权益汇总"""
    user_id = int(request.user.id)
    data = await my_access_service.get_summary(db=db, user_id=user_id, force_refresh=force_refresh)
    return response_base.success(data=data)


@router.get(
    '/subscription-ledger',
    summary='我的订阅流水',
    dependencies=[DependsJwtAuth],
)
async def get_my_subscription_ledger(
    request: Request,
    db: CurrentSession,
    limit: Annotated[int, Query(ge=1, le=100, description='数量上限')] = 50,
) -> ResponseSchemaModel[list[GetMySubscriptionLedger]]:
    """我的订阅流水"""
    user_id = int(request.user.id)
    data = await my_access_service.get_subscription_ledger(db=db, user_id=user_id, limit=limit)
    return response_base.success(data=data)


@router.get(
    '/quota',
    summary='我的配额余额',
    dependencies=[DependsJwtAuth],
)
async def get_my_quota(
    request: Request,
    db: CurrentSession,
    entitlement_code: Annotated[str, Query(description='权益编码')],
    cycle_type: Annotated[CycleType, Query(description='周期类型')] = CycleType.MONTHLY,
    scope_key: Annotated[str, Query(description='业务范围键')] = 'global',
) -> ResponseSchemaModel[GetQuotaBalance]:
    """我的配额余额"""
    user_id = int(request.user.id)
    cycle_key = build_cycle_key(cycle_type)
    balance = await ledger_service.get_balance(
        db,
        user_id=user_id,
        entitlement_code=entitlement_code,
        scope_key=scope_key,
        cycle_type=cycle_type,
        cycle_key=cycle_key,
    )
    return response_base.success(
        data=GetQuotaBalance(
            user_id=user_id,
            entitlement_code=entitlement_code,
            scope_key=scope_key,
            cycle_type=cycle_type,
            cycle_key=cycle_key,
            balance=balance,
            used=0,
        )
    )
