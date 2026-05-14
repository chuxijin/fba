#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.vocab.crud.crud_book import book_dao, book_word_dao
from backend.app.vocab.model import VocabBook
from backend.app.vocab.schema.book import (
    BatchAddWordsParam,
    BatchRemoveWordsParam,
    CreateBookParam,
    CreateBookWordParam,
    GetBookDetail,
    UpdateBookParam,
)
from backend.common.exception import errors
from backend.common.pagination import paging_data


class BookService:
    """词书管理服务类"""

    @staticmethod
    async def create_book(*, db: AsyncSession, user_id: int, obj: CreateBookParam) -> GetBookDetail:
        """
        创建词书

        :param db: 数据库会话
        :param user_id: 创建者用户 ID
        :param obj: 创建参数
        :return:
        """
        book = await book_dao.create_model(db, obj, created_by=user_id, creator_id=user_id, commit=False)
        await db.commit()
        await db.refresh(book)
        return GetBookDetail.model_validate(book)

    @staticmethod
    async def update_book(*, db: AsyncSession, pk: int, obj: UpdateBookParam) -> int:
        """
        更新词书

        :param db: 数据库会话
        :param pk: 词书 ID
        :param obj: 更新参数
        :return:
        """
        book = await book_dao.select_model(db, pk)
        if not book:
            raise errors.NotFoundError(msg='词书不存在')

        update_data = obj.model_dump(exclude_unset=True)
        if not update_data:
            return 0
        return await book_dao.update_model(db, pk, update_data)

    @staticmethod
    async def delete_book(*, db: AsyncSession, pk: int) -> int:
        """
        删除词书

        :param db: 数据库会话
        :param pk: 词书 ID
        :return:
        """
        book = await book_dao.select_model(db, pk)
        if not book:
            raise errors.NotFoundError(msg='词书不存在')
        return await book_dao.delete_model(db, pk)

    @staticmethod
    async def get_book(*, db: AsyncSession, pk: int) -> VocabBook:
        """
        获取词书实体

        :param db: 数据库会话
        :param pk: 词书 ID
        :return:
        """
        book = await book_dao.select_model(db, pk)
        if not book:
            raise errors.NotFoundError(msg='词书不存在')
        return book

    @staticmethod
    async def get_book_detail(*, db: AsyncSession, pk: int) -> GetBookDetail:
        """
        获取词书详情

        :param db: 数据库会话
        :param pk: 词书 ID
        :return:
        """
        book = await BookService.get_book(db=db, pk=pk)
        return GetBookDetail.model_validate(book)

    @staticmethod
    async def get_book_list(
        *,
        db: AsyncSession,
        category: str | None = None,
        keyword: str | None = None,
        is_official: bool | None = None,
        status: int | None = None,
    ) -> dict[str, Any]:
        """
        获取词书列表

        :param db: 数据库会话
        :param category: 分类过滤
        :param keyword: 搜索关键词
        :param is_official: 是否官方
        :param status: 状态过滤
        :return:
        """
        stmt = await book_dao.get_select(category=category, keyword=keyword, is_official=is_official, status=status)
        return await paging_data(db, stmt)

    @staticmethod
    async def add_words_to_book(*, db: AsyncSession, pk: int, obj: BatchAddWordsParam) -> int:
        """
        批量添加单词到词书

        :param db: 数据库会话
        :param pk: 词书 ID
        :param obj: 批量添加参数
        :return:
        """
        book = await book_dao.select_model(db, pk)
        if not book:
            raise errors.NotFoundError(msg='词书不存在')

        added = 0
        for word_id in obj.word_ids:
            existing = await book_word_dao.get_by_book_and_word(db, pk, word_id)
            if not existing:
                await book_word_dao.create_model(
                    db, CreateBookWordParam(book_id=pk, word_id=word_id), commit=False
                )
                added += 1

        if added > 0:
            book.word_count = book.word_count + added
            await db.commit()
        return added

    @staticmethod
    async def remove_words_from_book(*, db: AsyncSession, pk: int, obj: BatchRemoveWordsParam) -> int:
        """
        批量从词书移除单词

        :param db: 数据库会话
        :param pk: 词书 ID
        :param obj: 批量移除参数
        :return:
        """
        book = await book_dao.select_model(db, pk)
        if not book:
            raise errors.NotFoundError(msg='词书不存在')

        removed = 0
        for word_id in obj.word_ids:
            existing = await book_word_dao.get_by_book_and_word(db, pk, word_id)
            if existing:
                await db.delete(existing)
                removed += 1

        if removed > 0:
            book.word_count = max(0, book.word_count - removed)
            await db.commit()
        return removed


book_service: BookService = BookService()
