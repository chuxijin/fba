#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.vocab.model import VocabUserWord


class CRUDUserWord(CRUDPlus[VocabUserWord]):
    """用户单词 FSRS 状态数据库操作类"""

    async def get_by_user_and_word(self, db: AsyncSession, user_id: int, word_id: int) -> VocabUserWord | None:
        """
        获取用户与单词的学习状态

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param word_id: 单词 ID
        :return:
        """
        return await self.select_model_by_column(db, user_id__eq=user_id, word_id__eq=word_id)

    async def get_due_words(
        self,
        db: AsyncSession,
        user_id: int,
        now: datetime,
        limit: int = 200,
    ) -> list[VocabUserWord]:
        """
        获取用户待复习的单词（due <= now）

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param now: 当前时间
        :param limit: 上限
        :return:
        """
        stmt = (
            select(VocabUserWord)
            .where(VocabUserWord.user_id == user_id, VocabUserWord.due <= now)
            .order_by(VocabUserWord.due.asc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_learned_word_ids(self, db: AsyncSession, user_id: int) -> set[int]:
        """
        获取用户已学过的所有单词 ID

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = select(VocabUserWord.word_id).where(VocabUserWord.user_id == user_id)
        result = await db.execute(stmt)
        return set(result.scalars().all())

    async def count_by_state(self, db: AsyncSession, user_id: int) -> dict[int, int]:
        """
        按状态统计用户单词数

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = (
            select(VocabUserWord.state, func.count())
            .where(VocabUserWord.user_id == user_id)
            .group_by(VocabUserWord.state)
        )
        result = await db.execute(stmt)
        return {row[0]: row[1] for row in result.all()}

    async def get_starred_select(self, user_id: int) -> Select:
        """
        获取用户收藏的单词列表

        :param user_id: 用户 ID
        :return:
        """
        return (
            select(VocabUserWord)
            .where(VocabUserWord.user_id == user_id, VocabUserWord.is_starred == True)  # noqa: E712
            .order_by(VocabUserWord.created_time.desc())
        )


user_word_dao: CRUDUserWord = CRUDUserWord(VocabUserWord)
