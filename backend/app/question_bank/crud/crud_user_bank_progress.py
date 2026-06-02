#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from typing import Any

import sqlalchemy as sa

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model.practice import SessionQuestion
from backend.app.question_bank.model.progress import UserBankQuestionProgress
from backend.app.question_bank.model.question import QuestionPlacement
from backend.common.enums import DataBaseType
from backend.core.conf import settings
from backend.utils.timezone import timezone


class CRUDUserBankQuestionProgress(CRUDPlus[UserBankQuestionProgress]):
    """用户内容题目进度汇总数据库操作类"""

    @staticmethod
    def _normalize_record_ids(record_ids: list[int]) -> list[int]:
        """
        规范化记录 ID 列表

        :param record_ids: 答题记录 ID 列表
        :return:
        """
        return list(dict.fromkeys(record_id for record_id in record_ids if record_id > 0))

    async def upsert_by_record_ids(self, db: AsyncSession, *, record_ids: list[int]) -> int:
        """
        按答题记录同步用户内容题目进度

        :param db: 数据库会话
        :param record_ids: 答题记录 ID 列表
        :return:
        """
        normalized_record_ids = self._normalize_record_ids(record_ids)
        if not normalized_record_ids:
            return 0

        if DataBaseType.postgresql == settings.DATABASE_TYPE:
            return await self._upsert_by_record_ids_postgresql(db, record_ids=normalized_record_ids)

        return await self._upsert_by_record_ids_fallback(db, record_ids=normalized_record_ids)

    async def _upsert_by_record_ids_postgresql(self, db: AsyncSession, *, record_ids: list[int]) -> int:
        """
        PostgreSQL 批量同步用户内容题目进度

        :param db: 数据库会话
        :param record_ids: 答题记录 ID 列表
        :return:
        """
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        progress = UserBankQuestionProgress
        answered_time = func.coalesce(SessionQuestion.updated_time, SessionQuestion.created_time, func.now())
        correct_time = sa.case(
            (
                SessionQuestion.is_correct.is_(True),
                func.coalesce(SessionQuestion.judged_at, SessionQuestion.updated_time, SessionQuestion.created_time, func.now()),
            ),
            else_=None,
        )
        source_stmt = (
            select(
                SessionQuestion.user_id,
                QuestionPlacement.bank_id,
                SessionQuestion.question_id,
                SessionQuestion.placement_id,
                QuestionPlacement.chapter_id,
                SessionQuestion.session_id,
                SessionQuestion.id.label('last_session_question_id'),
                func.coalesce(SessionQuestion.is_correct, False).label('is_correct'),
                func.coalesce(SessionQuestion.created_time, func.now()).label('first_answered_time'),
                answered_time.label('last_answered_time'),
                correct_time.label('last_correct_time'),
                func.coalesce(SessionQuestion.created_time, func.now()).label('created_time'),
                answered_time.label('updated_time'),
            )
            .join(QuestionPlacement, QuestionPlacement.id == SessionQuestion.placement_id)
            .where(
                SessionQuestion.id.in_(record_ids),
                SessionQuestion.user_answer.isnot(None),
            )
        )
        stmt = pg_insert(progress).from_select(
            [
                'user_id',
                'bank_id',
                'question_id',
                'placement_id',
                'chapter_id',
                'last_session_id',
                'last_session_question_id',
                'is_correct',
                'first_answered_time',
                'last_answered_time',
                'last_correct_time',
                'created_time',
                'updated_time',
            ],
            source_stmt,
        )
        excluded = stmt.excluded
        update_values = {
            'placement_id': excluded.placement_id,
            'chapter_id': excluded.chapter_id,
            'last_session_id': excluded.last_session_id,
            'last_session_question_id': excluded.last_session_question_id,
            'is_correct': sa.or_(progress.is_correct.is_(True), excluded.is_correct.is_(True)),
            'first_answered_time': func.least(progress.first_answered_time, excluded.first_answered_time),
            'last_answered_time': func.greatest(progress.last_answered_time, excluded.last_answered_time),
            'last_correct_time': sa.case(
                (progress.last_correct_time.is_(None), excluded.last_correct_time),
                (excluded.last_correct_time.is_(None), progress.last_correct_time),
                else_=func.greatest(progress.last_correct_time, excluded.last_correct_time),
            ),
            'updated_time': timezone.now(),
        }
        stmt = stmt.on_conflict_do_update(
            constraint='uq_user_bank_question_progress',
            set_=update_values,
        )
        result = await db.execute(stmt)
        await db.flush()
        return int(result.rowcount or 0)

    async def _upsert_by_record_ids_fallback(self, db: AsyncSession, *, record_ids: list[int]) -> int:
        """
        通用数据库同步用户内容题目进度

        :param db: 数据库会话
        :param record_ids: 答题记录 ID 列表
        :return:
        """
        source_stmt = (
            select(
                SessionQuestion.user_id,
                QuestionPlacement.bank_id,
                SessionQuestion.question_id,
                SessionQuestion.placement_id,
                QuestionPlacement.chapter_id,
                SessionQuestion.session_id,
                SessionQuestion.id.label('last_session_question_id'),
                SessionQuestion.is_correct,
                SessionQuestion.created_time,
                SessionQuestion.updated_time,
                SessionQuestion.judged_at,
            )
            .join(QuestionPlacement, QuestionPlacement.id == SessionQuestion.placement_id)
            .where(
                SessionQuestion.id.in_(record_ids),
                SessionQuestion.user_answer.isnot(None),
            )
        )
        rows = (await db.execute(source_stmt)).all()
        affected_count = 0
        for row in rows:
            progress = await self.select_model_by_column(
                db,
                user_id=row.user_id,
                bank_id=row.bank_id,
                question_id=row.question_id,
            )
            answered_time = row.updated_time or row.created_time or timezone.now()
            last_correct_time = None
            if row.is_correct is True:
                last_correct_time = row.judged_at or answered_time

            if progress is None:
                db.add(UserBankQuestionProgress(
                    user_id=row.user_id,
                    bank_id=row.bank_id,
                    question_id=row.question_id,
                    placement_id=row.placement_id,
                    chapter_id=row.chapter_id,
                    last_session_id=row.session_id,
                    last_session_question_id=row.last_session_question_id,
                    is_correct=row.is_correct is True,
                    first_answered_time=row.created_time or answered_time,
                    last_answered_time=answered_time,
                    last_correct_time=last_correct_time,
                ))
                affected_count += 1
                continue

            progress.placement_id = row.placement_id
            progress.chapter_id = row.chapter_id
            progress.last_session_id = row.session_id
            progress.last_session_question_id = row.last_session_question_id
            progress.is_correct = progress.is_correct or row.is_correct is True
            progress.first_answered_time = min(progress.first_answered_time, row.created_time or answered_time)
            progress.last_answered_time = max(progress.last_answered_time, answered_time)
            if last_correct_time is not None:
                if progress.last_correct_time is None:
                    progress.last_correct_time = last_correct_time
                else:
                    progress.last_correct_time = max(progress.last_correct_time, last_correct_time)
            affected_count += 1

        await db.flush()
        return affected_count

    async def get_answer_correct_maps(
        self,
        db: AsyncSession,
        *,
        user_id: int,
        bank_ids: list[int],
    ) -> tuple[dict[int, int], dict[int, int]]:
        """
        获取内容作答和答对数量映射

        :param db: 数据库会话
        :param user_id: 用户 ID
        :param bank_ids: 内容 ID 列表
        :return:
        """
        normalized_bank_ids = list(dict.fromkeys(bank_id for bank_id in bank_ids if bank_id > 0))
        if not normalized_bank_ids:
            return {}, {}

        stmt = (
            select(
                self.model.bank_id,
                func.count(),
                func.count(sa.case((self.model.is_correct.is_(True), 1))),
            )
            .where(
                self.model.user_id == user_id,
                self.model.bank_id.in_(normalized_bank_ids),
            )
            .group_by(self.model.bank_id)
        )
        rows = (await db.execute(stmt)).all()
        answer_map = {int(bank_id): int(answer_count or 0) for bank_id, answer_count, _ in rows}
        correct_map = {int(bank_id): int(correct_count or 0) for bank_id, _, correct_count in rows}
        return answer_map, correct_map

    async def delete_by_user(self, db: AsyncSession, *, user_id: int) -> int:
        """
        删除用户内容题目进度

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        stmt = delete(self.model).where(self.model.user_id == user_id)
        result = await db.execute(stmt)
        return int(result.rowcount or 0)

    async def get_select_by_user(self, *, user_id: int) -> sa.Select[tuple[Any]]:
        """
        获取用户内容题目进度查询表达式

        :param user_id: 用户 ID
        :return:
        """
        return select(self.model).where(self.model.user_id == user_id)


user_bank_progress_dao: CRUDUserBankQuestionProgress = CRUDUserBankQuestionProgress(UserBankQuestionProgress)
