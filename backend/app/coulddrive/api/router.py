#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.coulddrive.api.v1.file import router as file_router
from backend.app.coulddrive.api.v1.user import router as user_router
from backend.core.conf import settings

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)

v1.include_router(file_router)
v1.include_router(user_router)