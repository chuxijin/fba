#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.core.conf import settings
from backend.plugin.agents.api.v1.grading import router as grading_router

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)

v1.include_router(grading_router, prefix='/agents/grading', tags=['Agent - 批改'])
