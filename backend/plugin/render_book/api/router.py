#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.core.conf import settings
from backend.plugin.render_book.api.v1.render import router as render_router

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)
v1.include_router(render_router, prefix='/render-books', tags=['题本渲染'])
