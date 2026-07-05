#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.gongkao.crud.crud_hanyu_wordbook import hanyu_wordbook_dao
from backend.app.gongkao.crud.crud_hanyu_wordbook_entry import hanyu_wordbook_entry_dao
from backend.app.gongkao.model import GkHanyuWordbook, GkHanyuWordbookEntry
from backend.app.gongkao.schema.hanyu_wordbook import AddHanyuWordbookEntryParam, HanyuWordbookParam


class HanyuWordbookService:
    """词语本服务类"""

    @staticmethod
    async def create_wordbook(
        *, db: AsyncSession, teacher_id: int, obj: HanyuWordbookParam
    ) -> GkHanyuWordbook:
        """
        创建词语本

        :param db: 数据库会话
        :param teacher_id: 老师用户 ID
        :param obj: 创建参数
        :return:
        """
        book = await hanyu_wordbook_dao.create_model(
            db, obj, teacher_id=teacher_id, created_by=teacher_id
        )
        await db.flush()
        await db.refresh(book)
        return book

    @staticmethod
    async def get_wordbooks_by_teacher(
        *, db: AsyncSession, teacher_id: int
    ) -> list[GkHanyuWordbook]:
        """
        获取老师的所有词语本

        :param db: 数据库会话
        :param teacher_id: 老师用户 ID
        :return:
        """
        return await hanyu_wordbook_dao.get_by_teacher(db, teacher_id)

    @staticmethod
    async def add_entry(
        *, db: AsyncSession, book_id: int, obj: AddHanyuWordbookEntryParam
    ) -> GkHanyuWordbookEntry:
        """
        向词语本中添加词语条目

        :param db: 数据库会话
        :param book_id: 词语本 ID
        :param obj: 条目参数
        :return:
        """
        entry = await hanyu_wordbook_entry_dao.create_model(
            db, obj, wordbook_id=book_id
        )
        await db.flush()
        await db.refresh(entry)
        return entry

    @staticmethod
    async def list_entries(
        *, db: AsyncSession, book_id: int
    ) -> list[GkHanyuWordbookEntry]:
        """
        获取词语本的所有条目

        :param db: 数据库会话
        :param book_id: 词语本 ID
        :return:
        """
        return await hanyu_wordbook_entry_dao.get_by_book(db, book_id)


hanyu_wordbook_service: HanyuWordbookService = HanyuWordbookService()