#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import List
from datetime import datetime, timedelta

from sqlalchemy import Select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.mcp_service.model.mcp_search_log import McpSearchLog
from backend.plugin.mcp_service.schema.mcp_resource import CreateMcpSearchLogParam


class CRUDMcpSearchLog(CRUDPlus[McpSearchLog]):
    """MCP搜索日志CRUD操作类"""

    async def create(self, db: AsyncSession, obj: CreateMcpSearchLogParam) -> None:
        """
        创建搜索日志

        :param db: 数据库会话
        :param obj: 创建搜索日志参数
        """
        await self.create_model(db, obj, commit=True)

    async def get_search_stats(
        self,
        db: AsyncSession,
        days: int = 7
    ) -> dict:
        """
        获取搜索统计信息

        :param db: 数据库会话
        :param days: 统计天数
        :return: 统计信息
        """
        start_date = datetime.now() - timedelta(days=days)
        
        # 总搜索次数
        total_searches = await db.scalar(
            Select(func.count(McpSearchLog.id))
            .where(McpSearchLog.created_time >= start_date)
        )
        
        # 平均响应时间
        avg_response_time = await db.scalar(
            Select(func.avg(McpSearchLog.response_time))
            .where(McpSearchLog.created_time >= start_date)
        )
        
        # 热门搜索词
        popular_queries = await db.execute(
            Select(
                McpSearchLog.query,
                func.count(McpSearchLog.id).label('count')
            )
            .where(McpSearchLog.created_time >= start_date)
            .group_by(McpSearchLog.query)
            .order_by(func.count(McpSearchLog.id).desc())
            .limit(10)
        )
        
        return {
            'total_searches': total_searches or 0,
            'avg_response_time': round(avg_response_time or 0, 2),
            'popular_queries': [
                {'query': row.query, 'count': row.count}
                for row in popular_queries
            ]
        }

    async def get_list(
        self,
        db: AsyncSession,
        limit: int = 20
    ) -> List[McpSearchLog]:
        """
        获取搜索日志列表

        :param db: 数据库会话
        :param limit: 返回数量限制
        :return: 搜索记录列表
        """
        stmt = (
            self.select_model
            .order_by(McpSearchLog.created_time.desc())
            .limit(limit)
        )
        
        result = await db.execute(stmt)
        return result.scalars().all()

    async def delete_by_days(
        self,
        db: AsyncSession,
        days: int = 30
    ) -> int:
        """
        按天数删除旧日志

        :param db: 数据库会话
        :param days: 保留天数
        :return: 删除的记录数
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        
        return await self.delete_model_by_column(
            db, 
            allow_multiple=True,
            created_time__lt=cutoff_date
        )


# 创建CRUD实例
mcp_search_log_dao = CRUDMcpSearchLog(McpSearchLog) 