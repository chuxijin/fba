#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.mcp.model.search_log import McpSearchLog


class CRUDMcpSearchLog(CRUDPlus[McpSearchLog]):
    """MCP 搜索日志 CRUD（App 版）"""

    async def create(self, db: AsyncSession, obj: Any) -> None:
        await self.create_model(db, obj, commit=True)


mcp_search_log_dao = CRUDMcpSearchLog(McpSearchLog)


