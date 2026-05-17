#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.growth.api.v1.account import router as account_router
from backend.app.growth.api.v1.experience_rule import router as rule_router
from backend.app.growth.api.v1.my import router as my_router
from backend.core.conf import settings

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)

v1.include_router(rule_router, prefix='/growth/experience-rules', tags=['经验规则'])
v1.include_router(account_router, prefix='/growth/accounts', tags=['经验账户管理'])
v1.include_router(my_router, prefix='/growth/my', tags=['我的成长'])

router = v1
