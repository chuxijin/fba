#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging

from collections.abc import Sequence

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model import SessionQuestion
from backend.utils.timezone import timezone

log = logging.getLogger(__name__)


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
        if not items:
            return

        now = timezone.now()
        rows: list[dict] = []
        for item in items:
            row = dict(item)
            row['session_id'] = session_id
            row.setdefault('created_time', now)
            row.setdefault('updated_time', None)
            rows.append(row)

        stmt = (
            pg_insert(SessionQuestion)
            .values(rows)
            .on_conflict_do_nothing(index_elements=['session_id', 'question_id'])
        )
        result = await db.execute(stmt)
        inserted_count = result.rowcount if result.rowcount is not None else -1
        if inserted_count >= 0 and inserted_count < len(rows):
            log.warning(
                'SessionQuestion batch_create skipped duplicates: session_id=%s inserted=%s skipped=%s',
                session_id,
                inserted_count,
                len(rows) - inserted_count,
            )
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
