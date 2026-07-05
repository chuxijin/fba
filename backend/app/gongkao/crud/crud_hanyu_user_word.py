#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.gongkao.model import GkHanyuUserWord


class CRUDHanyuUserWord(CRUDPlus[GkHanyuUserWord]):
    """用户词语 FSRS 状态数据库操作类"""

    async def get_by_user_and_word(self, db: AsyncSession, user_id: int, hanyu_id: int) -> GkHanyuUserWord | None:
        """
        获取用户在某词语的学习状态

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param hanyu_id: 汉语词汇 ID
        :return:
        """
        return await self.select_model_by_column(db, user_id=user_id, hanyu_id=hanyu_id)

    async def get_due_words(
        self,
        db: AsyncSession,
        user_id: int,
        now: datetime,
        limit: int = 200,
    ) -> list[GkHanyuUserWord]:
        """
        获取用户待复习的词语（due <= now）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param now: 当前时间
        :param limit: 上限
        :return:
        """
        stmt = (
            select(GkHanyuUserWord)
            .where(GkHanyuUserWord.user_id == user_id, GkHanyuUserWord.due <= now)
            .order_by(GkHanyuUserWord.due.asc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_learned_hanyu_ids(self, db: AsyncSession, user_id: int) -> set[int]:
        """
        获取用户已学过的所有词语 ID

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = select(GkHanyuUserWord.hanyu_id).where(GkHanyuUserWord.user_id == user_id)
        result = await db.execute(stmt)
        return set(result.scalars().all())

    async def count_by_state(self, db: AsyncSession, user_id: int) -> dict[int, int]:
        """
        按状态统计用户词语数

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = (
            select(GkHanyuUserWord.state, func.count())
            .where(GkHanyuUserWord.user_id == user_id)
            .group_by(GkHanyuUserWord.state)
        )
        result = await db.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    async def count_today_new(
        self, db: AsyncSession, user_id: int, today_start: datetime, today_end: datetime
    ) -> int:
        """
        获取今日新学词语数

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param today_start: 今日开始时间
        :param today_end: 今日结束时间
        :return:
        """
        stmt = select(func.count()).where(
            GkHanyuUserWord.user_id == user_id,
            GkHanyuUserWord.created_time >= today_start,
            GkHanyuUserWord.created_time < today_end,
        )
        result = await db.execute(stmt)
        return result.scalar() or 0


hanyu_user_word_dao: CRUDHanyuUserWord = CRUDHanyuUserWord(GkHanyuUserWord)
