#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

from sqlalchemy import DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from backend.common.model import Base, id_key


class McpSearchLog(Base):
    """MCP搜索日志表"""

    __tablename__ = "mcp_search_log"

    id: Mapped[id_key] = mapped_column(init=False)

    query: Mapped[str] = mapped_column(String(500), nullable=False, comment="搜索查询")
    client_ip: Mapped[str | None] = mapped_column(String(45), nullable=True, default=None, comment="客户端IP")
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True, default=None, comment="用户代理")

    result_count: Mapped[int] = mapped_column(Integer, default=0, comment="结果数量")
    response_time: Mapped[int] = mapped_column(Integer, default=0, comment="响应时间(毫秒)")

    created_time: Mapped[DateTime] = mapped_column(DateTime, default=func.now(), comment="创建时间", init=False)

    __table_args__ = (
        Index('idx_mcp_search_log_query', 'query'),
        Index('idx_mcp_search_log_created_time', 'created_time'),
        Index('idx_mcp_search_log_client_ip', 'client_ip'),
    )


