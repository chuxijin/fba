#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.vocab.api.v1.admin import router as admin_router
from backend.app.vocab.api.v1.checkin import router as checkin_router
from backend.app.vocab.api.v1.group import router as group_router
from backend.app.vocab.api.v1.setting import router as setting_router
from backend.app.vocab.api.v1.study import router as study_router
from backend.core.conf import settings

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)

v1.include_router(admin_router)
v1.include_router(study_router)
v1.include_router(group_router)
v1.include_router(checkin_router)
v1.include_router(setting_router)
