#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from pydantic import BaseModel, Field


class SearchResourceParam(BaseModel):
    """搜索资源参数"""

    query: str = Field(..., description="核心检索短语")
    limit: int = Field(5, ge=1, le=50, description="返回条数")
    cloud_types: str | None = Field(None, description="逗号分隔的网盘类型如 quark,baidu,aliyun,123，当前仅 quark")
    external_search: bool = Field(True, description="是否在本地无结果时启用外部搜索")


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


