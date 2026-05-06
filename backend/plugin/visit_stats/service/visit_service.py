#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from backend.plugin.visit_stats.crud import visit_log_dao, visit_stats_dao
from backend.plugin.visit_stats.schema import VisitStatsResponse
from backend.utils.timezone import timezone


class VisitService:
    """访问统计服务"""

    @staticmethod
    async def record_visit(
        *,
        db: AsyncSession,
        ip_address: str,
        user_agent: str | None = None,
        referer: str | None = None,
        path: str | None = None,
    ) -> None:
        """记录一次访问"""
        await visit_log_dao.create_log(
            db=db,
            ip_address=ip_address,
            user_agent=user_agent,
            referer=referer,
            path=path,
        )

    @staticmethod
    async def get_stats(*, db: AsyncSession) -> VisitStatsResponse:
        """获取访问统计"""
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)

        # 获取今日实时数据
        today_pv = await visit_log_dao.count_today_pv(db)
        today_uv = await visit_log_dao.count_today_uv(db)
        recent_active = await visit_log_dao.count_recent_active(db, minutes=5)

        # 获取昨日数据（从汇总表）
        yesterday_stats = await visit_stats_dao.get_by_date(db, yesterday)
        yesterday_pv = yesterday_stats.pv if yesterday_stats else 0
        yesterday_uv = yesterday_stats.uv if yesterday_stats else 0

        # 获取汇总数据
        month_pv = await visit_stats_dao.get_month_pv(db)
        total_pv = await visit_stats_dao.get_total_pv(db)

        # 加上今日数据
        month_pv += today_pv
        total_pv += today_pv

        return VisitStatsResponse(
            recent_active=recent_active,
            today_uv=today_uv,
            today_pv=today_pv,
            yesterday_uv=yesterday_uv,
            yesterday_pv=yesterday_pv,
            month_pv=month_pv,
            total_pv=total_pv,
        )

    @staticmethod
    async def flush_daily_stats(*, db: AsyncSession, target_date: date | None = None) -> None:
        """
        汇总指定日期的统计数据（通常由定时任务在每日凌晨调用，汇总昨日数据）
        """
        from sqlalchemy import func, select

        from backend.plugin.visit_stats.model import VisitLog

        if target_date is None:
            target_date = timezone.now().date() - timedelta(days=1)

        # 统计指定日期的 PV/UV
        pv_stmt = select(func.count(VisitLog.id)).where(VisitLog.visit_date == target_date)
        uv_stmt = select(func.count(func.distinct(VisitLog.ip_address))).where(
            VisitLog.visit_date == target_date
        )

        pv_result = await db.execute(pv_stmt)
        uv_result = await db.execute(uv_stmt)

        pv = pv_result.scalar() or 0
        uv = uv_result.scalar() or 0

        # 更新汇总表
        await visit_stats_dao.upsert_stats(db, target_date, pv, uv)


visit_service: VisitService = VisitService()
