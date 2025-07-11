#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from sqlalchemy import String, Text, Integer, DateTime, Boolean, Index
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from backend.common.model import Base, id_key


class McpSearchLog(Base):
    """MCP搜索日志表"""
    
    __tablename__ = "mcp_search_log"
    
    id: Mapped[id_key] = mapped_column(init=False)
    
    # 搜索信息
    query: Mapped[str] = mapped_column(String(500), nullable=False, comment="搜索查询")
    
    # 客户端信息（无默认值的字段放前面）
    client_ip: Mapped[str | None] = mapped_column(String(45), nullable=True, default=None, comment="客户端IP")
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True, default=None, comment="用户代理")
    
    # 搜索结果（有默认值的字段放后面）
    result_count: Mapped[int] = mapped_column(Integer, default=0, comment="结果数量")
    response_time: Mapped[int] = mapped_column(Integer, default=0, comment="响应时间(毫秒)")
    
    # 时间戳
    created_time: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), comment="创建时间", init=False)
    
    # 索引定义
    __table_args__ = (
        Index('idx_mcp_search_log_query', 'query'),
        Index('idx_mcp_search_log_created_time', 'created_time'),
        Index('idx_mcp_search_log_client_ip', 'client_ip'),
    ) 