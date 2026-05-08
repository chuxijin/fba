#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.vocab.model import VocabReviewLog


class CRUDReviewLog(CRUDPlus[VocabReviewLog]):
    """复习日志数据库操作类"""

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
        stmt = (
            select(
                func.count(func.distinct(VocabReviewLog.word_id)).label('total_words'),
                func.sum(VocabReviewLog.duration_ms).label('total_duration_ms'),
            )
            .where(
                VocabReviewLog.user_id == user_id,
                VocabReviewLog.reviewed_at >= today_start,
                VocabReviewLog.reviewed_at < today_end,
            )
        )
        result = await db.execute(stmt)
        row = result.one()
        return {
            'total_words': row.total_words or 0,
            'total_duration_ms': row.total_duration_ms or 0,
        }

    async def get_select_by_user(
        self,
        user_id: int,
        word_id: int | None = None,
    ) -> Select:
        """
        获取用户复习日志列表

        :param user_id: 用户 ID
        :param word_id: 单词 ID 过滤
        :return:
        """
        stmt = select(VocabReviewLog).where(VocabReviewLog.user_id == user_id)
        if word_id is not None:
            stmt = stmt.where(VocabReviewLog.word_id == word_id)
        return stmt.order_by(VocabReviewLog.reviewed_at.desc())


review_log_dao: CRUDReviewLog = CRUDReviewLog(VocabReviewLog)
