#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.mcp.api.v1 import router as mcp_v1
from backend.core.conf import settings

# 使用全局 V1 前缀，与项目其余模块保持一致
v1 = APIRouter(prefix=settings.FASTAPI_API_V1_PATH)

v1.include_router(mcp_v1)


