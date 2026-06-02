#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select
from sqlalchemy_crud_plus import CRUDPlus

from backend.app.question_bank.model import PracticeAIEvaluation


class CRUDPracticeAIEvaluation(CRUDPlus[PracticeAIEvaluation]):
    """练习 AI 评估数据库操作类"""

    async def create(self, db: AsyncSession, obj: dict) -> PracticeAIEvaluation:
        """
        创建 AI 评估结果

        :param db: 数据库会话
        :param obj: 评估数据
        :return:
        """
        new_model = self.model(**obj)
        db.add(new_model)
        await db.flush()
        await db.refresh(new_model)
        return new_model

    async def get(self, db: AsyncSession, evaluation_id: int) -> PracticeAIEvaluation | None:
        """
        获取评估结果

        :param db: 数据库会话
        :param evaluation_id: 评估结果 ID
        :return:
        """
        return await self.select_model(db, evaluation_id)

    async def get_latest_question_eval(
        self,
        db: AsyncSession,
        *,
        session_question_id: int,
    ) -> PracticeAIEvaluation | None:
        """
        获取记录最新单题评估

        :param db: 数据库会话
        :param session_question_id: 作答记录 ID
        :return:
        """
        stmt = (
            select(PracticeAIEvaluation)
            .where(
                PracticeAIEvaluation.session_question_id == session_question_id,
                PracticeAIEvaluation.target_type == 'question_eval',
                PracticeAIEvaluation.is_latest.is_(True),
            )
            .order_by(PracticeAIEvaluation.id.desc())
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_latest_session_summary(
        self,
        db: AsyncSession,
        *,
        session_id: int,
    ) -> PracticeAIEvaluation | None:
        """
        获取会话最新总结

        :param db: 数据库会话
        :param session_id: 会话 ID
        :return:
        """
        stmt = (
            select(PracticeAIEvaluation)
            .where(
                PracticeAIEvaluation.session_id == session_id,
                PracticeAIEvaluation.target_type == 'session_summary',
                PracticeAIEvaluation.is_latest.is_(True),
            )
            .order_by(PracticeAIEvaluation.id.desc())
        )
        result = await db.execute(stmt)
        return result.scalars().first()

    async def list_latest_question_evals_by_session(
        self,
        db: AsyncSession,
        *,
        session_id: int,
    ) -> Sequence[PracticeAIEvaluation]:
        """
        获取会话下最新单题评估

        :param db: 数据库会话
        :param session_id: 会话 ID
        :return:
        """
        stmt = (
            select(PracticeAIEvaluation)
            .where(
                PracticeAIEvaluation.session_id == session_id,
                PracticeAIEvaluation.target_type == 'question_eval',
                PracticeAIEvaluation.is_latest.is_(True),
            )
            .order_by(PracticeAIEvaluation.session_question_id.asc(), PracticeAIEvaluation.id.desc())
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    async def mark_record_not_latest(self, db: AsyncSession, *, session_question_id: int) -> int:
        """
        将记录历史评估标记为非最新

        :param db: 数据库会话
        :param session_question_id: 作答记录 ID
        :return:
        """
        return await self.update_model_by_column(
            db,
            {'is_latest': False},
            session_question_id=session_question_id,
            target_type='question_eval',
            is_latest=True,
        )

    async def mark_session_summary_not_latest(self, db: AsyncSession, *, session_id: int) -> int:
        """
        将会话历史总结标记为非最新

        :param db: 数据库会话
        :param session_id: 会话 ID
        :return:
        """
        return await self.update_model_by_column(
            db,
            {'is_latest': False},
            session_id=session_id,
            target_type='session_summary',
            is_latest=True,
        )

    async def get_select(self, *, user_id: int | None = None, session_id: int | None = None) -> Select:
        """
        获取评估列表查询表达式

        :param user_id: 用户 ID
        :param session_id: 会话 ID
        :return:
        """
        stmt = select(PracticeAIEvaluation)

        if user_id is not None:
            stmt = stmt.where(PracticeAIEvaluation.user_id == user_id)
        if session_id is not None:
            stmt = stmt.where(PracticeAIEvaluation.session_id == session_id)

        return stmt.order_by(PracticeAIEvaluation.id.desc())


practice_ai_evaluation_dao: CRUDPracticeAIEvaluation = CRUDPracticeAIEvaluation(PracticeAIEvaluation)
