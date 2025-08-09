#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.plugin.mcp_service.api.v1.mcp_resource import router as mcp_resource_router
from backend.plugin.mcp_service.api.v1.configs import router as mcp_configs_router

router = APIRouter(prefix='/mcp')

router.include_router(mcp_resource_router, tags=['MCP资源搜索'])
router.include_router(mcp_configs_router)
