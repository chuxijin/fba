#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model import SessionQuestion
from backend.common.enums import DataBaseType
from backend.core.conf import settings
from backend.utils.timezone import timezone

log = logging.getLogger(__name__)


class CRUDSessionQuestion(CRUDPlus[SessionQuestion]):
    """会话题目明细数据库操作类（含答题记录）"""

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

    async def get_records_by_session(self, db: AsyncSession, session_id: int) -> list[SessionQuestion]:
        """
        获取会话中已答题的记录（user_answer IS NOT NULL，按题序排列）

        :param db: 数据库会话
        :param session_id: 会话 ID
        :return:
        """
        stmt = (
            select(SessionQuestion)
            .where(SessionQuestion.session_id == session_id, SessionQuestion.user_answer.isnot(None))
            .order_by(SessionQuestion.seq_no.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

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

    async def batch_upsert_answer(self, db: AsyncSession, records: list[dict]) -> list[SessionQuestion]:
        """
        批量创建或更新答题数据（按 session_id + question_id 冲突更新，数据库级 upsert）

        :param db: 数据库会话
        :param records: 答题数据列表（含 session_id, question_id, user_answer, answer_time 等）
        :return:
        """
        if not records:
            return []

        now = timezone.now()
        for record in records:
            if 'created_time' not in record:
                record['created_time'] = now
            if 'updated_time' not in record:
                record['updated_time'] = now

        update_cols = ['user_answer', 'answer_time', 'updated_time']
        judge_update_cols = ['is_correct', 'score', 'judged_at', 'judge_version']
        for record in records:
            for col in judge_update_cols:
                if col in record and col not in update_cols:
                    update_cols.append(col)

        if DataBaseType.postgresql == settings.DATABASE_TYPE:
            stmt = pg_insert(SessionQuestion).values(records)
            stmt = stmt.on_conflict_do_update(
                constraint='uq_session_question_question',
                set_={col: stmt.excluded[col] for col in update_cols},
            )
            stmt = stmt.returning(SessionQuestion)
            result = await db.execute(stmt)
            await db.flush()
            return list(result.scalars().all())
        else:
            from sqlalchemy.dialects.mysql import insert as mysql_insert

            stmt = mysql_insert(SessionQuestion).values(records)
            stmt = stmt.on_duplicate_key_update(
                **{col: stmt.inserted[col] for col in update_cols},
            )
            await db.execute(stmt)
            await db.flush()

            session_id = records[0]['session_id']
            question_ids = [record['question_id'] for record in records]
            return await self.get_by_session_question_ids(db, session_id, question_ids)

    async def get_by_session_question_ids(
        self,
        db: AsyncSession,
        session_id: int,
        question_ids: list[int],
    ) -> list[SessionQuestion]:
        """
        获取会话中指定题目的记录

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param question_ids: 题目 ID 列表
        :return:
        """
        if not question_ids:
            return []

        stmt = (
            select(SessionQuestion)
            .where(
                SessionQuestion.session_id == session_id,
                SessionQuestion.question_id.in_(question_ids),
            )
            .order_by(SessionQuestion.seq_no.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def count_answered_by_session(self, db: AsyncSession, session_id: int) -> int:
        """获取会话中已答题的数量"""
        stmt = select(func.count()).where(
            SessionQuestion.session_id == session_id,
            SessionQuestion.user_answer.isnot(None),
        )
        result = await db.execute(stmt)
        return result.scalar() or 0

    async def get_answered_progress_by_session(self, db: AsyncSession, session_id: int) -> tuple[int, int]:
        """
        获取会话已答题进度

        :param db: 数据库会话
        :param session_id: 会话 ID
        :return:
        """
        stmt = select(
            func.count(SessionQuestion.id),
            func.coalesce(func.sum(SessionQuestion.answer_time), 0),
        ).where(
            SessionQuestion.session_id == session_id,
            SessionQuestion.user_answer.isnot(None),
        )
        row = (await db.execute(stmt)).one()
        return int(row[0] or 0), int(row[1] or 0)

    async def get_by_session_and_question(
        self, db: AsyncSession, session_id: int, question_id: int
    ) -> SessionQuestion | None:
        """
        获取特定会话中的题目记录

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param question_id: 题目 ID
        :return:
        """
        return await self.select_model_by_column(db, session_id=session_id, question_id=question_id)

    async def get_by_session_and_seq(
        self, db: AsyncSession, session_id: int, seq_no: int
    ) -> SessionQuestion | None:
        """
        获取特定会话中指定题序的记录

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param seq_no: 题序
        :return:
        """
        return await self.select_model_by_column(db, session_id=session_id, seq_no=seq_no)

    async def get_user_question_history(
        self, db: AsyncSession, user_id: int, question_id: int
    ) -> list[SessionQuestion]:
        """
        获取用户对某题目的所有答题历史

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param question_id: 题目 ID
        :return:
        """
        stmt = (
            select(SessionQuestion)
            .where(
                SessionQuestion.user_id == user_id,
                SessionQuestion.question_id == question_id,
                SessionQuestion.user_answer.isnot(None),
            )
            .order_by(SessionQuestion.created_time.desc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def update_judge_result(
        self,
        db: AsyncSession,
        sq_id: int,
        *,
        is_correct: bool,
        score: Decimal | None = None,
        full_score: Decimal | None = None,
        judged_at: datetime | None = None,
        judge_version: str | None = None,
    ) -> int:
        """
        更新判题结果

        :param db: 数据库会话
        :param sq_id: 会话题目 ID
        :param is_correct: 是否正确
        :param score: 得分
        :param full_score: 满分
        :param judged_at: 判题时间
        :param judge_version: 判题规则版本
        :return:
        """
        update_data: dict = {'is_correct': is_correct}
        if score is not None:
            update_data['score'] = score
        if full_score is not None:
            update_data['full_score'] = full_score
        if judged_at is not None:
            update_data['judged_at'] = judged_at
        if judge_version is not None:
            update_data['judge_version'] = judge_version

        return await self.update_model(db, sq_id, update_data)

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

    async def get_select(
        self,
        user_id: int | None = None,
        session_id: int | None = None,
        question_id: int | None = None,
        placement_id: int | None = None,
        is_correct: bool | None = None,
        has_answer: bool | None = None,
    ) -> Select:
        """
        获取会话题目列表查询表达式

        :param user_id: 用户 ID
        :param session_id: 会话 ID
        :param question_id: 题目 ID
        :param placement_id: 挂载 ID
        :param is_correct: 是否正确
        :param has_answer: 是否有答案（True=已答, False=未答）
        :return:
        """
        stmt = select(SessionQuestion)

        if user_id is not None:
            stmt = stmt.where(SessionQuestion.user_id == user_id)
        if session_id is not None:
            stmt = stmt.where(SessionQuestion.session_id == session_id)
        if question_id is not None:
            stmt = stmt.where(SessionQuestion.question_id == question_id)
        if placement_id is not None:
            stmt = stmt.where(SessionQuestion.placement_id == placement_id)
        if is_correct is not None:
            stmt = stmt.where(SessionQuestion.is_correct == is_correct)
        if has_answer is True:
            stmt = stmt.where(SessionQuestion.user_answer.isnot(None))
        elif has_answer is False:
            stmt = stmt.where(SessionQuestion.user_answer.is_(None))

        stmt = stmt.order_by(SessionQuestion.created_time.desc())
        return stmt


session_question_dao: CRUDSessionQuestion = CRUDSessionQuestion(SessionQuestion)
