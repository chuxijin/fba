#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Annotated, Any, List

from fastapi import APIRouter, Depends

from backend.app.mcp.schema.resource import McpSearchResult, SearchResourceParam
from backend.app.mcp.service.mcp_server_builder import get_registered_tools
from backend.app.mcp.service.resource_search_service import perform_resource_search
from backend.common.response.response_schema import ResponseSchemaModel, response_base

router = APIRouter()


@router.get("/tools", summary="列出 MCP 工具")
async def list_mcp_tools() -> dict[str, Any]:
    """列出已注册的 MCP 工具名称与描述"""
    return {"tools": get_registered_tools()}


@router.get("/info", summary="MCP 服务信息")
async def mcp_info() -> dict[str, str]:
    """返回 MCP SSE 入口提示，路径保持与参考项目一致（根级）"""
    return {"sse_entry": "/sse", "post_message": "/messages/"}


@router.post("/search", summary="搜索资源", response_model=ResponseSchemaModel[List[McpSearchResult]])
async def search_mcp_resources(
    search_param: Annotated[SearchResourceParam, Depends()],
) -> ResponseSchemaModel[List[McpSearchResult]]:
    """根据查询参数搜索 MCP 资源库"""
    results = await perform_resource_search(
        query=search_param.query,
        limit=search_param.limit,
        cloud_types=search_param.cloud_types,
        enable_external_search=search_param.external_search,
    )
    return response_base.success(data=results)

