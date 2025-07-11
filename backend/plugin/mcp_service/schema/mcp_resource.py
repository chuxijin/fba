#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class McpSearchParam(BaseModel):
    """搜索参数"""
    query: str = Field(..., description="搜索关键词")
    limit: int = Field(10, description="返回数量限制", ge=1, le=50)


class McpSearchResult(BaseModel):
    """搜索结果"""
    remark: str = Field(..., description="备注")
    description: str = Field(..., description="描述")
    url: str = Field(..., description="资源链接")


class McpSearchResponse(BaseModel):
    """搜索响应"""
    query: str = Field(..., description="搜索查询")
    total: int = Field(..., description="结果总数")
    results: List[McpSearchResult] = Field(..., description="搜索结果列表")
    response_time: int = Field(..., description="响应时间(毫秒)")
    keywords: List[str] = Field(..., description="分词关键词")


class CreateMcpSearchLogParam(BaseModel):
    """创建搜索日志参数"""
    query: str = Field(..., description="搜索查询")
    result_count: int = Field(..., description="结果数量")
    response_time: int = Field(..., description="响应时间(毫秒)")
    client_ip: str | None = Field(None, description="客户端IP")
    user_agent: str | None = Field(None, description="用户代理") 