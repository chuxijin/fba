#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.cms.api.v1.admin import router as admin_router
from backend.app.cms.api.v1.slot import router as slot_router
from backend.core.conf import settings

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)

v1.include_router(slot_router)
v1.include_router(admin_router)
