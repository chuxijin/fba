#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from datetime import datetime
from decimal import Decimal

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model import PracticeRecord
from backend.common.enums import DataBaseType
from backend.core.conf import settings
from backend.utils.timezone import timezone


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
        获取会话的所有答题记录（按题序排列）

        :param db: 数据库会话
        :param session_id: 会话 ID
        :return:
        """
        stmt = (
            select(PracticeRecord)
            .where(PracticeRecord.session_id == session_id)
            .order_by(PracticeRecord.seq_no.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_session_question_ids(
        self,
        db: AsyncSession,
        session_id: int,
        question_ids: list[int],
    ) -> list[PracticeRecord]:
        """
        获取会话中指定题目的答题记录

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param question_ids: 题目 ID 列表
        :return:
        """
        if not question_ids:
            return []

        stmt = (
            select(PracticeRecord)
            .where(
                PracticeRecord.session_id == session_id,
                PracticeRecord.question_id.in_(question_ids),
            )
            .order_by(PracticeRecord.seq_no.asc())
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def count_by_session(self, db: AsyncSession, session_id: int) -> int:
        """获取会话的答题记录数"""
        stmt = select(func.count()).where(PracticeRecord.session_id == session_id)
        result = await db.execute(stmt)
        return result.scalar() or 0

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
        filters: dict = {'user_id': user_id}
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

    async def get_by_session_and_seq(
        self, db: AsyncSession, session_id: int, seq_no: int
    ) -> PracticeRecord | None:
        """
        获取特定会话中指定题序的答题记录

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param seq_no: 题序
        :return:
        """
        return await self.select_model_by_column(db, session_id=session_id, seq_no=seq_no)

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

    async def batch_upsert(self, db: AsyncSession, records: list[dict]) -> list[PracticeRecord]:
        """
        批量创建或更新答题记录（按 session_id + question_id 冲突更新，数据库级 upsert）

        :param db: 数据库会话
        :param records: 记录数据列表
        :return:
        """
        if not records:
            return []

        # 为所有记录添加时间戳
        now = timezone.now()
        for record in records:
            if 'created_time' not in record:
                record['created_time'] = now
            if 'updated_time' not in record:
                record['updated_time'] = now

        # 冲突时需要更新的列（排除构成唯一键的 session_id / question_id 和不可变的 user_id / created_time）
        update_cols = [
            'placement_id', 'seq_no', 'user_answer',
            'is_correct', 'score', 'full_score',
            'answer_time', 'judged_at', 'judge_version',
            'updated_time',
        ]

        if DataBaseType.postgresql == settings.DATABASE_TYPE:
            from sqlalchemy.dialects.postgresql import insert as pg_insert

            stmt = pg_insert(PracticeRecord).values(records)
            stmt = stmt.on_conflict_do_update(
                constraint='uq_practice_record_session_question',
                set_={col: stmt.excluded[col] for col in update_cols},
            )
            stmt = stmt.returning(PracticeRecord)
            result = await db.execute(stmt)
            await db.flush()
            return list(result.scalars().all())
        else:
            from sqlalchemy.dialects.mysql import insert as mysql_insert

            stmt = mysql_insert(PracticeRecord).values(records)
            stmt = stmt.on_duplicate_key_update(
                **{col: stmt.inserted[col] for col in update_cols},
            )

        await db.execute(stmt)
        await db.flush()

        session_id = records[0]['session_id']
        question_ids = [record['question_id'] for record in records]
        return await self.get_by_session_question_ids(db, session_id, question_ids)

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

    async def update_judge_result(
        self,
        db: AsyncSession,
        record_id: int,
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
        :param record_id: 记录 ID
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

        return await self.update_model(db, record_id, update_data)

    async def get_select(
        self,
        user_id: int | None = None,
        session_id: int | None = None,
        question_id: int | None = None,
        placement_id: int | None = None,
        is_correct: bool | None = None,
    ) -> Select:
        """
        获取答题记录列表查询表达式

        :param user_id: 用户 ID
        :param session_id: 会话 ID
        :param question_id: 题目 ID
        :param placement_id: 挂载 ID
        :param is_correct: 是否正确
        :return:
        """
        stmt = select(PracticeRecord)

        if user_id is not None:
            stmt = stmt.where(PracticeRecord.user_id == user_id)
        if session_id is not None:
            stmt = stmt.where(PracticeRecord.session_id == session_id)
        if question_id is not None:
            stmt = stmt.where(PracticeRecord.question_id == question_id)
        if placement_id is not None:
            stmt = stmt.where(PracticeRecord.placement_id == placement_id)
        if is_correct is not None:
            stmt = stmt.where(PracticeRecord.is_correct == is_correct)

        stmt = stmt.order_by(PracticeRecord.created_time.desc())
        return stmt


practice_record_dao: CRUDPracticeRecord = CRUDPracticeRecord(PracticeRecord)
