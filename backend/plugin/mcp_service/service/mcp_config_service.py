#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select

from backend.common.exception import errors
from backend.database.db import async_db_session
from backend.plugin.mcp_service.crud.crud_mcp_config import mcp_config_dao
from backend.plugin.mcp_service.model.mcp_config import McpConfig
from backend.plugin.mcp_service.schema.mcp_config import McpConfigIn


class McpConfigService:
    """MCP 配置服务类"""

    @staticmethod
    async def get(*, pk: int) -> McpConfig:
        """
        获取配置

        :param pk: 配置 ID
        :return:
        """
        async with async_db_session() as db:
            config = await mcp_config_dao.get(db, pk)
            if not config:
                raise errors.NotFoundError(msg='配置不存在')
            return config

    @staticmethod
    async def get_select(*, mcp: str | None = None) -> Select:
        """获取配置查询对象"""
        return await mcp_config_dao.get_list(mcp=mcp)

    @staticmethod
    async def create(*, obj: McpConfigIn) -> McpConfig:
        """
        创建配置

        :param obj: 配置参数
        :return:
        """
        async with async_db_session.begin() as db:
            existed = await mcp_config_dao.get_by_mcp(db, obj.mcp)
            if existed:
                raise errors.ConflictError(msg='配置已存在')
            return await mcp_config_dao.create_model(db, obj, commit=True)

    @staticmethod
    async def upsert(*, obj: McpConfigIn, created_by: int) -> McpConfig:
        """新增或更新配置"""
        async with async_db_session.begin() as db:
            return await mcp_config_dao.upsert(db, obj.mcp, obj.config, created_by)

    @staticmethod
    async def update(*, pk: int, obj: McpConfigIn) -> int:
        """
        更新配置

        :param pk: 配置 ID
        :param obj: 配置参数
        :return:
        """
        async with async_db_session.begin() as db:
            config = await mcp_config_dao.get(db, pk)
            if not config:
                raise errors.NotFoundError(msg='配置不存在')
            return await mcp_config_dao.update_model(db, pk, obj)

    @staticmethod
    async def delete(*, pks: list[int]) -> int:
        """批量删除配置"""
        async with async_db_session.begin() as db:
            return await mcp_config_dao.delete_model_by_column(db, allow_multiple=True, id__in=pks)


mcp_config_service = McpConfigService()


