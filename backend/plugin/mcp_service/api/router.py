#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from fastapi import APIRouter

from backend.plugin.mcp_service.api.v1 import mcp_resource

v1 = APIRouter(prefix='/mcp/v1')

v1.include_router(mcp_resource.router, prefix='/resources', tags=['MCP资源搜索']) 