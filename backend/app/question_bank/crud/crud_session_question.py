#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model import SessionQuestion


class CRUDSessionQuestion(CRUDPlus[SessionQuestion]):
    """会话题目明细数据库操作类"""

    async def list_by_session(self, db: AsyncSession, session_id: int) -> Sequence[SessionQuestion]:
        """
        获取会话的所有题目明细（按题序排列）

        :param db: 数据库会话
        :param session_id: 会话 ID
        :return:
        """
        stmt = (
            select(SessionQuestion)
            .where(SessionQuestion.session_id == session_id)
            .order_by(SessionQuestion.seq_no.asc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def batch_create(self, db: AsyncSession, session_id: int, items: list[dict]) -> None:
        """
        批量创建会话题目明细

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param items: 题目明细列表
        """
        for item in items:
            item['session_id'] = session_id
            db.add(SessionQuestion(**item))
        await db.flush()

    async def replace_by_session(self, db: AsyncSession, session_id: int, items: list[dict]) -> None:
        """
        全量替换会话题目明细（先删后插）

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param items: 新的题目明细列表
        """
        await self.delete_by_session(db, session_id)
        await self.batch_create(db, session_id, items)

    async def delete_by_session(self, db: AsyncSession, session_id: int) -> int:
        """
        删除会话的所有题目明细

        :param db: 数据库会话
        :param session_id: 会话 ID
        :return: 删除的记录数
        """
        stmt = delete(SessionQuestion).where(SessionQuestion.session_id == session_id)
        result = await db.execute(stmt)
        return result.rowcount


session_question_dao: CRUDSessionQuestion = CRUDSessionQuestion(SessionQuestion)
