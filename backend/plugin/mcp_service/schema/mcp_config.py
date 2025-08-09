#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from pydantic import BaseModel, Field


class McpConfigIn(BaseModel):
    """配置入参"""
    mcp: str = Field(..., description="MCP 名称")
    config: dict[str, Any] = Field(default_factory=dict, description="配置 JSON")


class McpConfigOut(BaseModel):
    """配置出参"""
    id: int = Field(..., description="主键 ID")
    mcp: str = Field(..., description="MCP 名称")
    config: dict[str, Any] = Field(default_factory=dict, description="配置 JSON")


