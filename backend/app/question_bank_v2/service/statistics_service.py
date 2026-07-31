from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.crud.crud_statistics import (
    question_statistics_dao,
    user_daily_statistics_dao,
    user_practice_statistics_dao,
)
from backend.app.question_bank_v2.model.practice import QbQuestionAttempt
from backend.app.question_bank_v2.service.difficulty_service import (
    difficulty_service,
    should_recalculate_difficulty,
)


class StatisticsService:
    """题库 V2 可重建统计投影服务类"""

    @staticmethod
    async def apply_attempt(
        *,
        db: AsyncSession,
        attempt: QbQuestionAttempt,
        max_score: Decimal,
    ) -> None:
        """在作答事务内同步维护题目、用户累计和每日统计"""
        is_first_practice_today = await user_daily_statistics_dao.apply_attempt(db, attempt=attempt)
        await user_practice_statistics_dao.apply_attempt(
            db,
            attempt=attempt,
            is_first_practice_today=is_first_practice_today,
        )
        question_statistics = await question_statistics_dao.apply_attempt(
            db,
            attempt=attempt,
            max_score=max_score,
        )
        if attempt.is_correct is not None and should_recalculate_difficulty(question_statistics.graded_count):
            await difficulty_service.recalculate(db=db, question_id=attempt.question_id)

    @staticmethod
    async def apply_session_submission(*, db: AsyncSession, user_id: int) -> None:
        """在会话首次交卷时累计有效会话数"""
        await user_practice_statistics_dao.increment_session(db, user_id=user_id)

    @staticmethod
    async def apply_delayed_grade(
        *,
        db: AsyncSession,
        attempt: QbQuestionAttempt,
        max_score: Decimal,
    ) -> None:
        """只补写延迟产生的判分维度，避免重复累计一次提交"""
        await user_daily_statistics_dao.apply_delayed_grade(db, attempt=attempt)
        await user_practice_statistics_dao.apply_delayed_grade(db, attempt=attempt)
        question_statistics = await question_statistics_dao.apply_delayed_grade(
            db,
            attempt=attempt,
            max_score=max_score,
        )
        if should_recalculate_difficulty(question_statistics.graded_count):
            await difficulty_service.recalculate(db=db, question_id=attempt.question_id)


statistics_service: StatisticsService = StatisticsService()
