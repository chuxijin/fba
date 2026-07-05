#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from fastapi import APIRouter

from backend.app.mcp.service.mcp_server_builder import get_registered_tools

router = APIRouter()


@router.get('/tools', summary='列出 MCP 工具')
async def list_mcp_tools() -> dict[str, Any]:
    """列出已注册的 MCP 工具名称与描述"""
    return {'tools': get_registered_tools()}


@router.get('/info', summary='MCP 服务信息')
async def mcp_info() -> dict[str, str]:
    """返回 MCP SSE 入口提示，路径保持与参考项目一致（根级）"""
    return {'sse_entry': '/sse', 'post_message': '/messages/'}
