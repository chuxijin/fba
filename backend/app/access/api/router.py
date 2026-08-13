#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.access.api.v1.dashboard import router as dashboard_router
from backend.app.access.api.v1.debug import router as debug_router
from backend.app.access.api.v1.domain import router as domain_router
from backend.app.access.api.v1.entitlement import router as entitlement_router
from backend.app.access.api.v1.grant import router as grant_router
from backend.app.access.api.v1.my import router as my_router
from backend.app.access.api.v1.pack import router as pack_router
from backend.app.access.api.v1.redeem import router as redeem_router
from backend.app.access.api.v1.rule import router as rule_router
from backend.app.access.api.v1.subscription import router as subscription_router
from backend.app.access.api.v1.template import router as template_router
from backend.app.access.api.v1.tier import router as tier_router
from backend.core.conf import settings

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)

v1.include_router(dashboard_router, prefix='/access/dashboard', tags=['订阅总览'])
v1.include_router(domain_router, prefix='/access/domains', tags=['领域字典'])
v1.include_router(entitlement_router, prefix='/access/entitlements', tags=['权益字典'])
v1.include_router(pack_router, prefix='/access/packs', tags=['权益包'])
v1.include_router(template_router, prefix='/access/templates', tags=['订阅模板'])
v1.include_router(tier_router, prefix='/access/tiers', tags=['会员档位'])
v1.include_router(subscription_router, prefix='/access/subscriptions', tags=['用户订阅'])
v1.include_router(rule_router, prefix='/access/rules', tags=['资源规则'])
v1.include_router(grant_router, prefix='/access/grants', tags=['直接授予'])
v1.include_router(redeem_router, prefix='/access/redeem', tags=['兑换配置'])
v1.include_router(my_router, prefix='/access/my', tags=['我的权益'])
v1.include_router(debug_router, prefix='/access/decide', tags=['权益决策调试'])

router = v1
