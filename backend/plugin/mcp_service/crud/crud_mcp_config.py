#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy import select, Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.mcp_service.model.mcp_config import McpConfig
from backend.plugin.mcp_service.schema.mcp_config import McpConfigIn


class CRUDMcpConfig(CRUDPlus[McpConfig]):
    """MCP 配置 CRUD"""

    async def get_list(self, mcp: str | None = None) -> Select:
        """
        获取配置列表查询对象

        :param mcp: MCP 名称（模糊匹配）
        :return:
        """
        filters: dict[str, Any] = {}
        if mcp is not None:
            filters['mcp__like'] = f'%{mcp}%'
        return await self.select_order('created_time', 'desc', **filters)

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
        # 直接构造模型以填充 created_by 字段（由上层事务提交）
        new_obj = McpConfig(mcp=mcp, config=config, created_by=created_by)
        db.add(new_obj)
        await db.flush()
        return new_obj

    async def get_by_mcp(self, db: AsyncSession, mcp: str) -> McpConfig | None:
        """按名称查询"""
        stmt = select(McpConfig).where(McpConfig.mcp == mcp)
        res = await db.execute(stmt)
        return res.scalar_one_or_none()


mcp_config_dao = CRUDMcpConfig(McpConfig)


