#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.quest.api.v1.admin import router as admin_router
from backend.app.quest.api.v1.quest import router as quest_router
from backend.core.conf import settings

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)

v1.include_router(quest_router)
v1.include_router(admin_router)
