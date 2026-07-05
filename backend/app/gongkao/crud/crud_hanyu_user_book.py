#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.gongkao.model import GkHanyuUserBook


class CRUDHanyuUserBook(CRUDPlus[GkHanyuUserBook]):
    """用户词语本学习记录数据库操作类"""

    async def get_by_user_and_book(self, db: AsyncSession, user_id: int, book_id: int) -> GkHanyuUserBook | None:
        """
        获取用户在某词语本的学习状态

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param book_id: 词语本 ID
        :return:
        """
        return await self.select_model_by_column(db, user_id=user_id, book_id=book_id)

    async def get_active_book(self, db: AsyncSession, user_id: int) -> GkHanyuUserBook | None:
        """
        获取用户当前在学的词语本

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        return await self.select_model_by_column(db, user_id__eq=user_id, is_active__eq=True)

    async def deactivate_all(self, db: AsyncSession, user_id: int) -> None:
        """
        将用户所有词语本设为非活跃

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = select(GkHanyuUserBook).where(
            GkHanyuUserBook.user_id == user_id,
            GkHanyuUserBook.is_active == True,  # noqa: E712
        )
        result = await db.execute(stmt)
        for ub in result.scalars().all():
            ub.is_active = False


hanyu_user_book_dao: CRUDHanyuUserBook = CRUDHanyuUserBook(GkHanyuUserBook)
