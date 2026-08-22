from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy import and_, exists, func, or_, select

from backend.app.question_bank_v2.model import (
    QbQuestion,
    QbQuestionAnswer,
    QbQuestionAttempt,
    QbQuestionStatistics,
    QbUserQuestionMastery,
)
from backend.plugin.agent.service.coach_intent import QUESTION_TYPE_HINTS

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class CoachRecommendationService:
    """按 YanShen 规则从 qbank_v2 生成下一题候选。"""

    async def recommend(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        module: str = 'overview',
        limit: int = 5,
        include_attempted: bool = False,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 20))
        attempt_exists = exists(
            select(QbQuestionAttempt.id).where(
                QbQuestionAttempt.user_id == user_id,
                QbQuestionAttempt.question_id == QbQuestion.id,
                QbQuestionAttempt.deleted == 0,
            )
        )
        stmt = (
            select(QbQuestion, QbUserQuestionMastery, QbQuestionStatistics)
            .join(QbQuestionAnswer, QbQuestionAnswer.question_id == QbQuestion.id)
            .outerjoin(
                QbUserQuestionMastery,
                and_(
                    QbUserQuestionMastery.user_id == user_id,
                    QbUserQuestionMastery.question_id == QbQuestion.id,
                    QbUserQuestionMastery.deleted == 0,
                ),
            )
            .outerjoin(QbQuestionStatistics, QbQuestionStatistics.question_id == QbQuestion.id)
            .where(
                QbQuestion.deleted == 0,
                QbQuestion.status == 'active',
                QbQuestionAnswer.grading_method == 'rubric',
                or_(QbQuestion.visibility.in_({'public', 'internal'}), QbQuestion.owner_id == user_id),
            )
        )
        if not include_attempted:
            stmt = stmt.where(~attempt_exists)
        hints = QUESTION_TYPE_HINTS.get(module, ())
        if hints:
            stmt = stmt.where(or_(*(QbQuestion.stem.like(f'%{hint}%') for hint in hints)))
        stmt = stmt.order_by(
            func.coalesce(QbUserQuestionMastery.mastery_score, 0).asc(),
            func.coalesce(QbQuestionStatistics.correct_rate, 0.5).asc(),
            func.coalesce(QbQuestion.difficulty, 3).asc(),
            QbQuestion.id.desc(),
        ).limit(limit * 3 if hints else limit)
        rows = list((await db.execute(stmt)).all())
        if hints and len(rows) < limit:
            return await self.recommend(
                db=db,
                user_id=user_id,
                module='overview',
                limit=limit,
                include_attempted=include_attempted,
            )
        return [
            self._to_payload(question, mastery, statistics, module)
            for question, mastery, statistics in rows[:limit]
        ]

    @staticmethod
    def _to_payload(question: QbQuestion, mastery: Any, statistics: Any, module: str) -> dict[str, Any]:
        return {
            'question_id': question.id,
            'code': question.code,
            'stem': str(question.stem or '')[:500],
            'question_type': question.question_type,
            'difficulty': float(question.difficulty) if question.difficulty is not None else None,
            'module': module,
            'mastery_score': float(mastery.mastery_score) if mastery and mastery.mastery_score is not None else None,
            'attempt_count': mastery.attempt_count if mastery else 0,
            'correct_rate': (
                float(statistics.correct_rate)
                if statistics and statistics.correct_rate is not None
                else None
            ),
            'reason': '优先补足当前薄弱或尚未训练的题型',
        }


coach_recommendation_service = CoachRecommendationService()
