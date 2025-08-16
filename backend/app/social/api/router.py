#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.core.conf import settings
from backend.app.social.api.v1.account import router as account_router
from backend.app.social.api.v1.work import router as work_router
from backend.app.social.api.v1.metric import router as metric_router


v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)

v1.include_router(account_router)
v1.include_router(work_router)
v1.include_router(metric_router)


