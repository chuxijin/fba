#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.mcp.crud.crud_config import mcp_config_dao
from backend.app.mcp.model.config import McpConfig
from backend.app.mcp.schema.config import UpsertMcpConfigParam, McpConfigItem, UpsertMcpConfigBatchParam
from backend.common.exception import errors


class McpConfigService:
    """配置服务"""

    async def get_list(self, db: AsyncSession, mcp: str | None, field: str | None) -> list[McpConfig]:
        stmt = await mcp_config_dao.get_list(mcp=mcp, field=field)
        res = await db.execute(stmt)
        return list(res.scalars().all())

    async def get(self, db: AsyncSession, config_id: int) -> McpConfig | None:
        return await mcp_config_dao.get(db, config_id)

    async def get_by_mcp_and_field(self, db: AsyncSession, mcp: str, field: str) -> McpConfig | None:
        return await mcp_config_dao.get_by_mcp_and_field(db, mcp, field)

    async def create(self, db: AsyncSession, data: UpsertMcpConfigParam, created_by: int) -> McpConfig:
        obj = await mcp_config_dao.get_by_mcp_and_field(db, data.mcp, data.field)
        if obj:
            raise errors.ConflictError(msg=f"配置 {data.mcp}:{data.field} 已存在")
        created = await mcp_config_dao.create(db, data.mcp, data.field, data.value, created_by)
        await db.commit()
        return created

    async def update(self, db: AsyncSession, data: UpsertMcpConfigParam, updated_by: int) -> McpConfig:
        obj = await mcp_config_dao.update(db, data.mcp, data.field, data.value, updated_by)
        if not obj:
            raise errors.NotFoundError(msg="配置不存在")
        await db.commit()
        return obj

    async def upsert_batch(self, db: AsyncSession, data: UpsertMcpConfigBatchParam, operator_id: int) -> list[McpConfig]:
        results: list[McpConfig] = []
        for it in data.items:
            exists = await mcp_config_dao.get_by_mcp_and_field(db, data.mcp, it.field)
            if exists:
                obj = await mcp_config_dao.update(db, data.mcp, it.field, it.value, operator_id)
            else:
                obj = await mcp_config_dao.create(db, data.mcp, it.field, it.value, operator_id)
            if obj:
                results.append(obj)
        if results:
            await db.commit()
        return results

    async def delete(self, db: AsyncSession, config_id: int) -> None:
        await mcp_config_dao.delete_model(db, config_id)
        await db.commit()


mcp_config_service = McpConfigService()


