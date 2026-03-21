#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.membership.api.v1.membership import router as membership_router
from backend.app.membership.api.v1.plan import router as plan_router
from backend.core.conf import settings

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)

v1.include_router(plan_router, prefix='/membership/plans', tags=['会员计划管理'])
v1.include_router(membership_router, prefix='/membership', tags=['会员服务'])
