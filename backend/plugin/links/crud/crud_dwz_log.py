#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.links.model import DwzLog
from backend.plugin.links.schema.dwz_log import CreateDwzLogParam
from backend.utils.timezone import timezone


class CRUDDwzLog(CRUDPlus[DwzLog]):
    """短网址访问日志数据库操作类"""

    async def create(self, db: AsyncSession, obj: CreateDwzLogParam, created_by: int = 0) -> DwzLog:
        """
        创建访问日志

        :param db: 数据库会话
        :param obj: 创建参数
        :param created_by: 创建者ID(匿名访问为0)
        :return:
        """
        log = DwzLog(
            dwz_id=obj.dwz_id,
            ip=obj.ip,
            platform=obj.platform,
            user_agent=obj.user_agent,
            referer=obj.referer,
            country=obj.country,
            city=obj.city,
            created_by=created_by,
        )
        db.add(log)
        await db.flush()
        await db.refresh(log)
        return log

    async def get_by_dwz_id(
        self,
        db: AsyncSession,
        dwz_id: int,
        *,
        limit: int = 100,
    ) -> Sequence[DwzLog]:
        """
        获取短网址的访问日志

        :param db: 数据库会话
        :param dwz_id: 短网址ID
        :param limit: 返回数量限制
        :return:
        """
        stmt = (
            select(self.model).where(self.model.dwz_id == dwz_id).order_by(self.model.created_time.desc()).limit(limit)
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def count_today(self, db: AsyncSession, dwz_id: int) -> int:
        """
        统计今日访问量

        :param db: 数据库会话
        :param dwz_id: 短网址ID
        :return:
        """
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        stmt = (
            select(func.count())
            .select_from(self.model)
            .where(self.model.dwz_id == dwz_id)
            .where(self.model.created_time >= today_start)
        )
        result = await db.execute(stmt)
        return result.scalar() or 0

    async def get_platform_stats(self, db: AsyncSession, dwz_id: int) -> dict[str, int]:
        """
        获取平台访问统计

        :param db: 数据库会话
        :param dwz_id: 短网址ID
        :return:
        """
        stmt = (
            select(self.model.platform, func.count().label('count'))
            .where(self.model.dwz_id == dwz_id)
            .where(self.model.platform.isnot(None))
            .group_by(self.model.platform)
        )
        result = await db.execute(stmt)
        rows = result.all()
        return {row.platform: row.count for row in rows}

    async def delete_by_dwz_id(self, db: AsyncSession, dwz_id: int) -> int:
        """
        删除短网址的所有访问日志

        :param db: 数据库会话
        :param dwz_id: 短网址ID
        :return:
        """
        return await self.delete_model_by_column(db, dwz_id=dwz_id)


dwz_log_dao: CRUDDwzLog = CRUDDwzLog(DwzLog)
