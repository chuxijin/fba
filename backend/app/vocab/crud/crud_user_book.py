#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.vocab.model import VocabUserBook


class CRUDUserBook(CRUDPlus[VocabUserBook]):
    """用户词书数据库操作类"""

    async def get_active_book(self, db: AsyncSession, user_id: int) -> VocabUserBook | None:
        """
        获取用户当前在学的词书

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await self.select_model_by_column(db, user_id__eq=user_id, is_active__eq=True)

    async def get_by_user_and_book(self, db: AsyncSession, user_id: int, book_id: int) -> VocabUserBook | None:
        """
        获取用户与词书的关联记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param book_id: 词书 ID
        :return:
        """
        return await self.select_model_by_column(db, user_id__eq=user_id, book_id__eq=book_id)

    async def deactivate_all(self, db: AsyncSession, user_id: int) -> None:
        """
        将用户所有词书设为非活跃

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = select(VocabUserBook).where(VocabUserBook.user_id == user_id, VocabUserBook.is_active == True)  # noqa: E712
        result = await db.execute(stmt)
        for ub in result.scalars().all():
            ub.is_active = False

    async def get_select_by_user(self, user_id: int) -> Select:
        """
        获取用户词书列表

        :param user_id: 用户 ID
        :return:
        """
        return (
            select(VocabUserBook)
            .where(VocabUserBook.user_id == user_id)
            .order_by(VocabUserBook.is_active.desc(), VocabUserBook.created_time.desc())
        )


user_book_dao: CRUDUserBook = CRUDUserBook(VocabUserBook)
