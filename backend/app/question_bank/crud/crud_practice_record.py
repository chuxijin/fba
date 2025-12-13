#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model import PracticeRecord


class CRUDPracticeRecord(CRUDPlus[PracticeRecord]):
    """答题记录数据库操作类"""

    async def get(self, db: AsyncSession, record_id: int) -> PracticeRecord | None:
        """
        获取答题记录详情

        :param db: 数据库会话
        :param record_id: 记录 ID
        :return:
        """
        return await self.select_model(db, record_id)

    async def get_by_session(self, db: AsyncSession, session_id: int) -> list[PracticeRecord]:
        """
        获取会话的所有答题记录

        :param db: 数据库会话
        :param session_id: 会话 ID
        :return:
        """
        stmt = await self.select_order('created_time', 'asc', session_id=session_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_user(
        self, db: AsyncSession, user_id: int, question_id: int | None = None
    ) -> list[PracticeRecord]:
        """
        获取用户的答题记录

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_id: 题目 ID
        :return:
        """
        filters = {'user_id': user_id}
        if question_id:
            filters['question_id'] = question_id

        stmt = await self.select_order('created_time', 'desc', **filters)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_session_and_question(
        self, db: AsyncSession, session_id: int, question_id: int
    ) -> PracticeRecord | None:
        """
        获取特定会话中的题目答题记录

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param question_id: 题目 ID
        :return:
        """
        return await self.select_model_by_column(db, session_id=session_id, question_id=question_id)

    async def create(self, db: AsyncSession, obj_dict: dict) -> PracticeRecord:
        """
        创建答题记录

        :param db: 数据库会话
        :param obj_dict: 记录数据
        :return:
        """
        new_record = self.model(**obj_dict)
        db.add(new_record)
        await db.flush()
        await db.refresh(new_record)
        return new_record

    async def batch_create(self, db: AsyncSession, records: list[dict]) -> None:
        """
        批量创建答题记录

        :param db: 数据库会话
        :param records: 记录数据列表
        :return:
        """
        for record_dict in records:
            new_record = self.model(**record_dict)
            db.add(new_record)

    async def delete_by_session(self, db: AsyncSession, session_id: int) -> int:
        """
        删除会话的所有答题记录

        :param db: 数据库会话
        :param session_id: 会话 ID
        :return: 删除的记录数
        """
        stmt = delete(PracticeRecord).where(PracticeRecord.session_id == session_id)
        result = await db.execute(stmt)
        return result.rowcount

    async def get_user_question_history(self, db: AsyncSession, user_id: int, question_id: int) -> list[PracticeRecord]:
        """
        获取用户对某题目的所有答题历史

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_id: 题目 ID
        :return:
        """
        stmt = await self.select_order('created_time', 'desc', user_id=user_id, question_id=question_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_select(
        self,
        user_id: int | None = None,
        session_id: int | None = None,
        question_id: int | None = None,
        is_correct: bool | None = None,
        bank_id: int | None = None,
        chapter_id: int | None = None,
    ) -> Select:
        """
        获取答题记录列表查询表达式

        :param user_id: 用户 ID
        :param session_id: 会话 ID
        :param question_id: 题目 ID
        :param is_correct: 是否正确
        :param bank_id: 题库 ID
        :param chapter_id: 章节 ID
        :return:
        """
        filters = {}

        if user_id:
            filters['user_id'] = user_id
        if session_id:
            filters['session_id'] = session_id
        if question_id:
            filters['question_id'] = question_id
        if is_correct is not None:
            filters['is_correct'] = is_correct
        if bank_id:
            filters['bank_id'] = bank_id
        if chapter_id:
            filters['chapter_id'] = chapter_id

        return await self.select_order('created_time', 'desc', **filters)


practice_record_dao: CRUDPracticeRecord = CRUDPracticeRecord(PracticeRecord)
