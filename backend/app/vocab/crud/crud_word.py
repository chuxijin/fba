#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.vocab.model import VocabDefinition, VocabExample, VocabWord


class CRUDWord(CRUDPlus[VocabWord]):
    """单词数据库操作类"""

    async def get_by_word(self, db: AsyncSession, word: str) -> VocabWord | None:
        """
        根据单词文本查找

        :param db: 数据库会话
        :param word: 单词文本
        :return:
        """
        return await self.select_model_by_column(db, word__eq=word)

    async def get_select(self, keyword: str | None = None) -> Select:
        """
        获取单词列表查询表达式

        :param keyword: 搜索关键词
        :return:
        """
        stmt = select(VocabWord)
        if keyword:
            stmt = stmt.where(VocabWord.word.like(f'%{keyword}%'))
        return stmt.order_by(VocabWord.word.asc())


class CRUDDefinition(CRUDPlus[VocabDefinition]):
    """释义数据库操作类"""

    async def get_by_word_id(self, db: AsyncSession, word_id: int) -> list[VocabDefinition]:
        """
        获取单词的所有释义

        :param db: 数据库会话
        :param word_id: 单词 ID
        :return:
        """
        stmt = (
            select(VocabDefinition).where(VocabDefinition.word_id == word_id).order_by(VocabDefinition.sort_order.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def delete_by_word_id(self, db: AsyncSession, word_id: int) -> None:
        """
        删除单词的所有释义

        :param db: 数据库会话
        :param word_id: 单词 ID
        :return:
        """
        objs = await self.get_by_word_id(db, word_id)
        for obj in objs:
            await db.delete(obj)


class CRUDExample(CRUDPlus[VocabExample]):
    """例句数据库操作类"""

    async def get_by_word_id(self, db: AsyncSession, word_id: int) -> list[VocabExample]:
        """
        获取单词的所有例句

        :param db: 数据库会话
        :param word_id: 单词 ID
        :return:
        """
        stmt = select(VocabExample).where(VocabExample.word_id == word_id).order_by(VocabExample.sort_order.asc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def delete_by_word_id(self, db: AsyncSession, word_id: int) -> None:
        """
        删除单词的所有例句

        :param db: 数据库会话
        :param word_id: 单词 ID
        :return:
        """
        objs = await self.get_by_word_id(db, word_id)
        for obj in objs:
            await db.delete(obj)


word_dao: CRUDWord = CRUDWord(VocabWord)
definition_dao: CRUDDefinition = CRUDDefinition(VocabDefinition)
example_dao: CRUDExample = CRUDExample(VocabExample)
