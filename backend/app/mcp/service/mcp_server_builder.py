#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Callable, Tuple

from typing import Any, Callable, Tuple

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.routing import Mount, Route

from backend.app.mcp.service.resource_search_service import register_resource_search_tools


_mcp: Any | None = None
_registered_tools_cache: list[dict[str, str]] | None = None


def _ensure_mcp() -> Any:
    """懒加载并构建 FastMCP 实例"""
    global _mcp
    if _mcp is not None:
        return _mcp

    # 运行时导入，避免编辑器无法解析导入
    from mcp.server.fastmcp import FastMCP  # type: ignore

    mcp = FastMCP("resource_search")
    # 注册工具
    register_resource_search_tools(mcp)

    # 缓存工具列表（避免访问内部私有对象）
    global _registered_tools_cache
    _registered_tools_cache = [
        {"name": "search_resources", "description": "搜索资源库（基于 yp_resource）"}
    ]
    _mcp = mcp
    return mcp


def get_registered_tools() -> list[dict[str, str]]:
    """返回已注册工具的名称与描述"""
    if _registered_tools_cache is not None:
        return _registered_tools_cache
    _ = _ensure_mcp()
    return _registered_tools_cache or []


def _create_starlette_app(mcp_server: Any, *, debug: bool = False) -> Starlette:
    """创建 Starlette 应用，挂载 SSE 传输与入口"""
    from mcp.server.sse import SseServerTransport  # type: ignore

    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> None:
        async with sse.connect_sse(
            request.scope,
            request.receive,
            request._send,  # noqa: SLF001
        ) as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )

    return Starlette(
        debug=debug,
        routes=[
            Route("/sse", endpoint=handle_sse),
            Mount("/messages/", app=sse.handle_post_message),
        ],
    )


def create_starlette_app(*, debug: bool = False) -> Starlette:
    """对外暴露：创建并返回内部 Starlette 应用。"""
    mcp_server: Any = _ensure_mcp()._mcp_server  # type: ignore[attr-defined]
    return _create_starlette_app(mcp_server, debug=debug)


def create_sse_components() -> Tuple[Callable[..., Any], Any]:
    """返回可以直接注册到 FastAPI 的 /sse 路由处理器与 /messages/ 挂载应用"""
    from mcp.server.sse import SseServerTransport  # type: ignore

    mcp_server: Any = _ensure_mcp()._mcp_server  # type: ignore[attr-defined]
    sse = SseServerTransport("/messages/")

    async def handle_sse(request: Request) -> None:
        async with sse.connect_sse(
            request.scope,
            request.receive,
            request._send,  # noqa: SLF001
        ) as (read_stream, write_stream):
            await mcp_server.run(
                read_stream,
                write_stream,
                mcp_server.create_initialization_options(),
            )

    return handle_sse, sse.handle_post_message


