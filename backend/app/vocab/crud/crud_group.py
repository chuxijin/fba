#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.vocab.model import VocabGroupWord, VocabWordGroup


class CRUDWordGroup(CRUDPlus[VocabWordGroup]):
    """学习组数据库操作类"""

    async def get_select_by_user(self, user_id: int) -> Select:
        """
        获取用户学习组列表

        :param user_id: 用户 ID
        :return:
        """
        return (
            select(VocabWordGroup)
            .where(VocabWordGroup.user_id == user_id)
            .order_by(VocabWordGroup.sort_order.asc(), VocabWordGroup.created_time.desc())
        )


class CRUDGroupWord(CRUDPlus[VocabGroupWord]):
    """学习组单词关联数据库操作类"""

    async def get_by_group_and_word(self, db: AsyncSession, group_id: int, word_id: int) -> VocabGroupWord | None:
        """
        获取学习组与单词的关联记录

        :param db: 数据库会话
        :param group_id: 学习组 ID
        :param word_id: 单词 ID
        :return:
        """
        return await self.select_model_by_column(db, group_id__eq=group_id, word_id__eq=word_id)

    async def get_word_ids_by_group(self, db: AsyncSession, group_id: int) -> list[int]:
        """
        获取学习组下所有单词 ID

        :param db: 数据库会话
        :param group_id: 学习组 ID
        :return:
        """
        stmt = select(VocabGroupWord.word_id).where(VocabGroupWord.group_id == group_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_select_by_group(self, group_id: int) -> Select:
        """
        获取学习组单词关联列表

        :param group_id: 学习组 ID
        :return:
        """
        return (
            select(VocabGroupWord).where(VocabGroupWord.group_id == group_id).order_by(VocabGroupWord.added_at.desc())
        )


word_group_dao: CRUDWordGroup = CRUDWordGroup(VocabWordGroup)
group_word_dao: CRUDGroupWord = CRUDGroupWord(VocabGroupWord)
