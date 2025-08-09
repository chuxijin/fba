#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.plugin.mcp_service.api.v1.configs.mcp_config import router as mcp_config_router

router = APIRouter(prefix='/configs')

router.include_router(mcp_config_router, tags=['MCP配置'])
