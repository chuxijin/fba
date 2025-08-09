#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.mcp.model.config import McpConfig


class CRUDMcpConfig(CRUDPlus[McpConfig]):
    """MCP 配置 CRUD（App 版）"""

    async def upsert(self, db: AsyncSession, mcp: str, config: dict[str, Any], created_by: int) -> McpConfig:
        """
        新增或更新配置

        :param db: 会话
        :param mcp: 名称
        :param config: JSON 配置
        :return:
        """
        stmt = select(McpConfig).where(McpConfig.mcp == mcp)
        res = await db.execute(stmt)
        obj = res.scalar_one_or_none()
        if obj:
            await self.update_model(db, obj.id, {"config": config}, commit=False)
            return obj
        new_obj = McpConfig(mcp=mcp, config=config, created_by=created_by)
        db.add(new_obj)
        await db.flush()
        return new_obj

    async def get_by_mcp(self, db: AsyncSession, mcp: str) -> McpConfig | None:
        stmt = select(McpConfig).where(McpConfig.mcp == mcp)
        res = await db.execute(stmt)
        return res.scalar_one_or_none()


mcp_config_dao = CRUDMcpConfig(McpConfig)


