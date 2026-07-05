#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.gongkao.model import GkHanyuReviewLog


class CRUDHanyuReviewLog(CRUDPlus[GkHanyuReviewLog]):
    """汉语复习日志数据库操作类"""

    async def count_today(
        self,
        db: AsyncSession,
        user_id: int,
        today_start: datetime,
        today_end: datetime,
    ) -> dict[str, int]:
        """
        统计用户今日学习数据

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param today_start: 今天开始时间
        :param today_end: 今天结束时间
        :return:
        """
        stmt = select(
            func.count(func.distinct(GkHanyuReviewLog.hanyu_id)).label('total_words'),
            func.sum(GkHanyuReviewLog.duration_ms).label('total_duration_ms'),
        ).where(
            GkHanyuReviewLog.user_id == user_id,
            GkHanyuReviewLog.reviewed_at >= today_start,
            GkHanyuReviewLog.reviewed_at < today_end,
        )
        result = await db.execute(stmt)
        row = result.one()
        return {
            'total_words': row.total_words or 0,
            'total_duration_ms': row.total_duration_ms or 0,
        }


hanyu_review_log_dao: CRUDHanyuReviewLog = CRUDHanyuReviewLog(GkHanyuReviewLog)
