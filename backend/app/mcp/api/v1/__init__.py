#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.app.mcp.api.v1.config import router as config_router
from backend.app.mcp.api.v1.mcp import router as mcp_router

router = APIRouter(prefix='/mcp')

router.include_router(config_router, tags=['MCP 配置管理'])
router.include_router(mcp_router, tags=['MCP 服务管理'])
