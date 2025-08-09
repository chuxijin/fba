#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pydantic import BaseModel, Field


class McpSearchParam(BaseModel):
    """搜索参数"""

    query: str = Field(..., description="关键词")
    limit: int = Field(5, ge=1, le=50, description="返回数量")


class McpSearchResult(BaseModel):
    """搜索结果"""

    remark: str = Field(..., description="备注")
    description: str = Field(..., description="描述")
    url: str = Field(..., description="链接")


class CreateMcpSearchLogParam(BaseModel):
    """创建搜索日志参数"""

    query: str = Field(..., description="搜索查询")
    result_count: int = Field(..., description="数量")
    response_time: int = Field(..., description="响应时间毫秒")
    client_ip: str | None = Field(None, description="IP")
    user_agent: str | None = Field(None, description="UA")


