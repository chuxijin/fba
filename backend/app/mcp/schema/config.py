#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from typing import Any

from pydantic import Field

from backend.common.schema import SchemaBase


class UpsertMcpConfigParam(SchemaBase):
    """配置入参"""

    mcp: str = Field(..., description="MCP 名称")
    field: str = Field(..., description="配置字段")
    value: dict[str, Any] = Field(default_factory=dict, description="配置值 JSON")


class McpConfigItem(SchemaBase):
    """配置项"""

    id: int = Field(description="ID")
    mcp: str = Field(description="MCP 名称")
    field: str = Field(description="配置字段")
    value: str = Field(description="配置值")


class GetMcpConfigListParam(SchemaBase):
    """配置查询参数"""

    mcp: str | None = Field(None, description="按 MCP 名称筛选")
    field: str | None = Field(None, description="按配置字段筛选")


class UpsertMcpConfigBatchItem(SchemaBase):
    """批量配置项"""

    field: str = Field(..., description="配置字段")
    value: dict[str, Any] = Field(default_factory=dict, description="配置值 JSON")


class UpsertMcpConfigBatchParam(SchemaBase):
    """批量配置入参"""

    mcp: str = Field(..., description="MCP 名称")
    items: list[UpsertMcpConfigBatchItem] = Field(default_factory=list, description="配置项列表")


