#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.mcp.model.config import McpConfig


class CRUDMcpConfig(CRUDPlus[McpConfig]):
    """MCP 配置 CRUD（App 版）"""

    async def create(self, db: AsyncSession, mcp: str, field: str, value: dict, created_by: int) -> McpConfig:
        """
        创建配置

        :param db: 会话
        :param mcp: MCP 名称
        :param field: 配置字段
        :param value: 配置值
        :param created_by: 创建人 ID
        :return:
        """
        stmt = select(McpConfig).where(and_(McpConfig.mcp == mcp, McpConfig.field == field))
        res = await db.execute(stmt)
        exists = res.scalar_one_or_none()
        if exists:
            return exists
        new_obj = McpConfig(mcp=mcp, field=field, value=value, created_by=created_by)
        db.add(new_obj)
        await db.flush()
        return new_obj

    async def update(self, db: AsyncSession, mcp: str, field: str, value: dict, updated_by: int) -> McpConfig | None:
        """
        更新配置

        :param db: 会话
        :param mcp: MCP 名称
        :param field: 配置字段
        :param value: 配置值
        :param updated_by: 更新人 ID
        :return:
        """
        stmt = select(McpConfig).where(and_(McpConfig.mcp == mcp, McpConfig.field == field))
        res = await db.execute(stmt)
        obj = res.scalar_one_or_none()
        if not obj:
            return None
        await self.update_model(db, obj.id, {'value': value, 'updated_by': updated_by}, commit=False)
        return obj

    async def get_by_mcp_and_field(self, db: AsyncSession, mcp: str, field: str) -> McpConfig | None:
        stmt = select(McpConfig).where(and_(McpConfig.mcp == mcp, McpConfig.field == field))
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    async def get_list(self, mcp: str | None, field: str | None):
        filters = {}
        if mcp is not None:
            filters['mcp__like'] = f'%{mcp}%'
        if field is not None:
            filters['field__like'] = f'%{field}%'
        return await self.select_order('created_time', 'desc', **filters)


mcp_config_dao = CRUDMcpConfig(McpConfig)
