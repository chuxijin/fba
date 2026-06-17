#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from contextlib import AsyncExitStack
from typing import Any, Optional, Tuple

from mcp import ClientSession


class MCPClient:
    """MCP 客户端：连接 SSE 服务器，列出工具并参与对话循环"""

    def __init__(self) -> None:
        self.session: Optional[ClientSession] = None
        self.exit_stack: AsyncExitStack = AsyncExitStack()
        self._streams_context = None
        self._session_context = None

    async def connect_to_sse_server(self, server_url: str) -> Tuple[list[dict[str, Any]], ClientSession]:
        """
        连接到运行 SSE 传输的 MCP 服务器

        :param server_url: 服务器 SSE 入口，如 http://localhost:8080/sse
        :return:
        """
        # 避免静态导入依赖导致类型检查报错，运行时按需导入
        from mcp.client.sse import sse_client  # type: ignore

        self._streams_context = sse_client(url=server_url)
        streams = await self._streams_context.__aenter__()

        self._session_context = ClientSession(*streams)
        self.session = await self._session_context.__aenter__()

        await self.session.initialize()

        response = await self.session.list_tools()
        tools = response.tools

        formatted_tools: list[dict[str, Any]] = []
        for tool in tools:
            properties: dict[str, Any] = {}
            for param_name, param_info in tool.inputSchema['properties'].items():
                param_data: dict[str, Any] = {
                    'type': param_info['type'],
                    'description': param_info.get('description', param_info.get('title', '')),
                }
                if param_info['type'] == 'array' and 'items' in param_info:
                    param_data['items'] = {'type': param_info['items'].get('type')}
                properties[param_name] = param_data

            formatted_tools.append({
                'type': 'function',
                'function': {
                    'name': tool.name,
                    'description': tool.description,
                    'parameters': {
                        'type': 'object',
                        'properties': properties,
                        'required': tool.inputSchema.get('required', []),
                    },
                },
            })

        return formatted_tools, self.session

    async def cleanup(self) -> None:
        """清理会话与流"""
        if self._session_context:
            await self._session_context.__aexit__(None, None, None)
        if self._streams_context:
            await self._streams_context.__aexit__(None, None, None)

    # 示例 OpenAI 客户端与对话循环已移除，如需自定义客户端可在外部按需实现
