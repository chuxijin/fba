#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from backend.app.question_bank.model import (
    PracticeAIEvaluation,
    PracticeSession,
    SessionQuestion,
    UserCheckIn,
    UserDailyRank,
    UserPracticeStats,
    WrongQuestionBook,
)
from backend.app.question_bank.crud.crud_user_bank_progress import user_bank_progress_dao
from backend.app.question_bank.schema.user_settings import PracticeDataResetResult
from backend.app.question_bank.service.wrong_question_service import WrongQuestionService
from backend.plugin.agents.model import AgentTask
from backend.plugin.agents.schema.report import AgentType


class PracticeDataResetService:
    """做题数据重置服务类"""

    @staticmethod
    def _affected_count(value: int | None) -> int:
        """
        规范化数据库影响行数

        :param value: 原始影响行数
        :return:
        """
        return int(value or 0)

    @staticmethod
    async def _clear_user_cache(user_id: int) -> None:
        """
        清理用户做题相关缓存

        :param user_id: 用户 ID
        :return:
        """
        await WrongQuestionService._clear_statistics_cache(user_id)

    @classmethod
    async def reset_user_practice_data(cls, *, db: AsyncSession, user_id: int) -> PracticeDataResetResult:
        """
        重置用户做题数据

        :param db: 数据库会话
        :param user_id: 用户 ID
        :return:
        """
        user_session_ids = select_user_session_ids(user_id)

        ai_evaluation_result = await db.execute(
            delete(PracticeAIEvaluation).where(PracticeAIEvaluation.user_id == user_id)
        )
        agent_task_result = await db.execute(
            delete(AgentTask).where(
                AgentTask.user_id == user_id,
                AgentTask.agent_type == AgentType.shenlun.value,
            )
        )
        practice_record_result = await db.execute(
            delete(SessionQuestion).where(SessionQuestion.user_id == user_id, SessionQuestion.user_answer.isnot(None))
        )
        progress_count = await user_bank_progress_dao.delete_by_user(db=db, user_id=user_id)
        session_question_result = await db.execute(
            delete(SessionQuestion).where(SessionQuestion.session_id.in_(user_session_ids))
        )
        practice_session_result = await db.execute(
            delete(PracticeSession).where(PracticeSession.user_id == user_id)
        )
        wrong_question_result = await db.execute(
            delete(WrongQuestionBook).where(WrongQuestionBook.user_id == user_id)
        )
        check_in_result = await db.execute(
            delete(UserCheckIn).where(UserCheckIn.user_id == user_id)
        )
        daily_rank_result = await db.execute(
            delete(UserDailyRank).where(UserDailyRank.user_id == user_id)
        )
        stats_result = await db.execute(
            update(UserPracticeStats)
            .where(UserPracticeStats.user_id == user_id)
            .values(
                total_count=0,
                correct_count=0,
                total_duration=0,
                practice_days=0,
                last_practice_date=None,
                streak_days=0,
            )
        )

        await db.flush()
        await cls._clear_user_cache(user_id)

        return PracticeDataResetResult(
            ai_evaluation_count=cls._affected_count(ai_evaluation_result.rowcount),
            agent_task_count=cls._affected_count(agent_task_result.rowcount),
            practice_record_count=cls._affected_count(practice_record_result.rowcount),
            progress_count=progress_count,
            session_question_count=cls._affected_count(session_question_result.rowcount),
            practice_session_count=cls._affected_count(practice_session_result.rowcount),
            wrong_question_count=cls._affected_count(wrong_question_result.rowcount),
            check_in_count=cls._affected_count(check_in_result.rowcount),
            daily_rank_count=cls._affected_count(daily_rank_result.rowcount),
            stats_reset_count=cls._affected_count(stats_result.rowcount),
        )


def select_user_session_ids(user_id: int) -> Select[tuple[int]]:
    """
    查询用户会话 ID 子查询

    :param user_id: 用户 ID
    :return:
    """
    return select(PracticeSession.id).where(PracticeSession.user_id == user_id)


practice_data_reset_service: PracticeDataResetService = PracticeDataResetService()
