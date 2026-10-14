#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.core.conf import settings
from backend.plugin.render_book.api.v1.public import router as public_router
from backend.plugin.render_book.api.v1.render import router as render_router

v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)
v1.include_router(render_router, prefix='/render-books', tags=['题本渲染'])
v1.include_router(public_router, prefix='/render-books/public', tags=['公开题本排版'])

