#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.vocab.model import VocabBook, VocabBookWord


class CRUDBook(CRUDPlus[VocabBook]):
    """词书数据库操作类"""

    async def get_select(
        self,
        category: str | None = None,
        keyword: str | None = None,
        is_official: bool | None = None,
        status: int | None = None,
    ) -> Select:
        """
        获取词书列表查询表达式

        :param category: 分类过滤
        :param keyword: 搜索关键词
        :param is_official: 是否官方
        :param status: 状态过滤
        :return:
        """
        stmt = select(VocabBook)

        conditions = []
        if category:
            conditions.append(VocabBook.category == category)
        if is_official is not None:
            conditions.append(VocabBook.is_official == is_official)
        if status is not None:
            conditions.append(VocabBook.status == status)
        if keyword:
            keyword_like = f'%{keyword}%'
            conditions.append(or_(VocabBook.name.like(keyword_like), VocabBook.description.like(keyword_like)))

        if conditions:
            stmt = stmt.where(and_(*conditions))

        return stmt.order_by(VocabBook.sort_order.asc(), VocabBook.created_time.desc())


class CRUDBookWord(CRUDPlus[VocabBookWord]):
    """词书单词关联数据库操作类"""

    async def get_by_book_and_word(self, db: AsyncSession, book_id: int, word_id: int) -> VocabBookWord | None:
        """
        根据词书和单词获取关联记录

        :param db: 数据库会话
        :param book_id: 词书 ID
        :param word_id: 单词 ID
        :return:
        """
        return await self.select_model_by_column(db, book_id__eq=book_id, word_id__eq=word_id)

    async def get_word_ids_by_book(self, db: AsyncSession, book_id: int) -> list[int]:
        """
        获取词书下所有单词 ID

        :param db: 数据库会话
        :param book_id: 词书 ID
        :return:
        """
        stmt = select(VocabBookWord.word_id).where(VocabBookWord.book_id == book_id).order_by(
            VocabBookWord.sort_order.asc()
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_select_by_book(self, book_id: int) -> Select:
        """
        获取词书单词关联列表

        :param book_id: 词书 ID
        :return:
        """
        return (
            select(VocabBookWord)
            .where(VocabBookWord.book_id == book_id)
            .order_by(VocabBookWord.sort_order.asc())
        )


book_dao: CRUDBook = CRUDBook(VocabBook)
book_word_dao: CRUDBookWord = CRUDBookWord(VocabBookWord)
