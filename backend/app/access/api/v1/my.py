#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated

from fastapi import APIRouter, Query, Request

from backend.app.access.constants import CycleType, SubscriptionStatus
from backend.app.access.engine.cycle import build_cycle_key
from backend.app.access.engine.ledger import ledger_service
from backend.app.access.schema.base import TimePeriodOutput
from backend.app.access.schema.ledger import GetQuotaBalance
from backend.app.access.schema.subscription import GetMySubscription
from backend.app.access.service.subscription_service import subscription_service
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
    subs = (
        await subscription_service.list_active(db=db, user_id=user_id)
        if only_active
        else await subscription_service.list_for_user(
            db=db, user_id=user_id, status=SubscriptionStatus.ACTIVE
        )
    )
    if not subs:
        return response_base.success(data=[])

    from backend.app.access.crud.crud_template import subscription_template_dao

    template_ids = list({sub.template_id for sub in subs})
    templates = await subscription_template_dao.select_models(db, id__in=template_ids)
    tpl_map = {tpl.id: tpl for tpl in templates}

    items: list[GetMySubscription] = []
    for sub in subs:
        tpl = tpl_map.get(sub.template_id)
        if not tpl:
            continue
        items.append(
            GetMySubscription(
                id=sub.id,
                template_code=tpl.code,
                template_name=tpl.name,
                cover_image=tpl.cover_image,
                valid_period=TimePeriodOutput.from_range(sub.valid_period),
                status=sub.status,
                created_time=sub.created_time,
            )
        )
    return response_base.success(data=items)


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
