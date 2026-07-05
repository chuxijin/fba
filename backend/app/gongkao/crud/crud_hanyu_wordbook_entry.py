#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.gongkao.model import GkHanyuWordbookEntry


class CRUDHanyuWordbookEntry(CRUDPlus[GkHanyuWordbookEntry]):
    """词语本条目数据库操作类"""

    async def get(self, db: AsyncSession, pk: int) -> GkHanyuWordbookEntry | None:
        """
        获取条目详情

        :param db: 数据库会话
        :param pk: 主键 ID
        :return:
        """
        return await self.select_model(db, pk)

    async def get_by_book(self, db: AsyncSession, book_id: int) -> list[GkHanyuWordbookEntry]:
        """
        获取词语本的所有条目

        :param db: 数据库会话
        :param book_id: 词语本 ID
        :return:
        """
        return await self.select_models(db, wordbook_id=book_id)

    async def get_hanyu_ids_by_book(self, db: AsyncSession, book_id: int) -> list[int]:
        """
        获取词语本中所有词语 ID

        :param db: 数据库会话
        :param book_id: 词语本 ID
        :return:
        """
        stmt = (
            select(GkHanyuWordbookEntry.hanyu_id)
            .where(GkHanyuWordbookEntry.wordbook_id == book_id)
            .order_by(GkHanyuWordbookEntry.sort_order)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())


hanyu_wordbook_entry_dao: CRUDHanyuWordbookEntry = CRUDHanyuWordbookEntry(GkHanyuWordbookEntry)
