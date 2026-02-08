#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date, timedelta
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.plugin.visit_stats.model.visit import VisitLog, VisitStats


class CRUDVisitLog(CRUDPlus[VisitLog]):
    """访问日志 CRUD"""

    async def create_log(
        self,
        db: AsyncSession,
        ip_address: str,
        user_agent: str | None = None,
        referer: str | None = None,
        path: str | None = None,
    ) -> VisitLog:
        """创建访问日志"""
        log = VisitLog(
            ip_address=ip_address,
            user_agent=user_agent[:500] if user_agent else None,
            referer=referer[:500] if referer else None,
            path=path[:255] if path else None,
        )
        db.add(log)
        await db.flush()
        return log

    async def count_today_pv(self, db: AsyncSession) -> int:
        """统计今日 PV"""
        today = date.today()
        stmt = select(func.count(VisitLog.id)).where(VisitLog.visit_date == today)
        result = await db.execute(stmt)
        return result.scalar() or 0

    async def count_today_uv(self, db: AsyncSession) -> int:
        """统计今日 UV（独立IP数）"""
        today = date.today()
        stmt = select(func.count(func.distinct(VisitLog.ip_address))).where(
            VisitLog.visit_date == today
        )
        result = await db.execute(stmt)
        return result.scalar() or 0

    async def count_recent_active(self, db: AsyncSession, minutes: int = 5) -> int:
        """统计最近活跃访客数（最近N分钟内有访问的独立IP）"""
        from backend.utils.timezone import timezone
        threshold = timezone.now() - timedelta(minutes=minutes)
        stmt = select(func.count(func.distinct(VisitLog.ip_address))).where(
            VisitLog.created_time >= threshold
        )
        result = await db.execute(stmt)
        return result.scalar() or 0


class CRUDVisitStats(CRUDPlus[VisitStats]):
    """访问统计 CRUD"""

    async def get_by_date(self, db: AsyncSession, stats_date: date) -> VisitStats | None:
        """按日期获取统计"""
        return await self.select_model_by_column(db, stats_date=stats_date)

    async def upsert_stats(self, db: AsyncSession, stats_date: date, pv: int, uv: int) -> VisitStats:
        """更新或插入统计"""
        stats = await self.get_by_date(db, stats_date)
        if stats:
            stats.pv = pv
            stats.uv = uv
        else:
            stats = VisitStats(stats_date=stats_date, pv=pv, uv=uv)
            db.add(stats)
        await db.flush()
        return stats

    async def get_total_pv(self, db: AsyncSession) -> int:
        """获取总 PV"""
        stmt = select(func.sum(VisitStats.pv))
        result = await db.execute(stmt)
        return result.scalar() or 0

    async def get_total_uv(self, db: AsyncSession) -> int:
        """获取总 UV"""
        stmt = select(func.sum(VisitStats.uv))
        result = await db.execute(stmt)
        return result.scalar() or 0

    async def get_month_pv(self, db: AsyncSession) -> int:
        """获取本月 PV"""
        today = date.today()
        first_day = today.replace(day=1)
        stmt = select(func.sum(VisitStats.pv)).where(VisitStats.stats_date >= first_day)
        result = await db.execute(stmt)
        return result.scalar() or 0


visit_log_dao: CRUDVisitLog = CRUDVisitLog(VisitLog)
visit_stats_dao: CRUDVisitStats = CRUDVisitStats(VisitStats)
