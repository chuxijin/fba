from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import delete, select

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.model.asset import QbQuestionAttemptAsset
from backend.app.question_bank_v2.model.evaluation import QbEvaluationRun
from backend.app.question_bank_v2.model.mastery import (
    QbQuestionAttemptKnowledgePoint,
    QbUserKnowledgeMastery,
)
from backend.app.question_bank_v2.model.practice import (
    QbPracticeSession,
    QbPracticeSessionItem,
    QbPracticeSessionResponse,
    QbQuestionAttempt,
)
from backend.app.question_bank_v2.model.review import (
    QbQuestionReview,
    QbQuestionReviewKnowledgePoint,
    QbQuestionReviewTag,
    QbReviewTag,
    QbWrongQuestionState,
)
from backend.app.question_bank_v2.model.statistics import (
    QbUserBankItemProgress,
    QbUserDailyStatistics,
    QbUserPracticeStatistics,
    QbUserQuestionMastery,
)


@dataclass
class PracticeDataResetResult:
    session_count: int = 0
    attempt_count: int = 0
    wrong_state_count: int = 0
    review_count: int = 0
    evaluation_count: int = 0
    user_tag_count: int = 0
    mastery_count: int = 0
    knowledge_mastery_count: int = 0
    attempt_knowledge_snapshot_count: int = 0
    bank_progress_count: int = 0
    practice_stats_count: int = 0
    daily_stats_count: int = 0


class PracticeDataResetService:

    @staticmethod
    async def reset_user_practice_data(
        *,
        db: AsyncSession,
        user_id: int,
    ) -> PracticeDataResetResult:
        r = PracticeDataResetResult()

        r.review_count += await _exec(db, delete(QbQuestionReviewKnowledgePoint).where(
            QbQuestionReviewKnowledgePoint.review_id.in_(
                select(QbQuestionReview.id).where(QbQuestionReview.user_id == user_id)
            )
        ))
        r.review_count += await _exec(db, delete(QbQuestionReviewTag).where(
            QbQuestionReviewTag.review_id.in_(
                select(QbQuestionReview.id).where(QbQuestionReview.user_id == user_id)
            )
        ))
        r.review_count += await _exec(db, delete(QbQuestionReview).where(
            QbQuestionReview.user_id == user_id
        ))

        r.wrong_state_count = await _exec(db, delete(QbWrongQuestionState).where(
            QbWrongQuestionState.user_id == user_id
        ))

        r.user_tag_count = await _exec(db, delete(QbReviewTag).where(
            QbReviewTag.user_id.isnot(None), QbReviewTag.user_id == user_id
        ))

        r.evaluation_count = await _exec(db, delete(QbEvaluationRun).where(
            QbEvaluationRun.user_id == user_id
        ))

        r.attempt_count += await _exec(db, delete(QbQuestionAttemptAsset).where(
            QbQuestionAttemptAsset.created_by == user_id
        ))
        r.attempt_knowledge_snapshot_count = await _exec(
            db,
            delete(QbQuestionAttemptKnowledgePoint).where(QbQuestionAttemptKnowledgePoint.user_id == user_id),
        )
        r.attempt_count += await _exec(db, delete(QbQuestionAttempt).where(QbQuestionAttempt.user_id == user_id))

        user_session_ids = select(QbPracticeSession.id).where(QbPracticeSession.user_id == user_id)
        r.attempt_count += await _exec(db, delete(QbPracticeSessionResponse).where(
            QbPracticeSessionResponse.session_id.in_(user_session_ids)
        ))
        r.attempt_count += await _exec(db, delete(QbPracticeSessionItem).where(
            QbPracticeSessionItem.session_id.in_(user_session_ids)
        ))

        r.session_count = await _exec(db, delete(QbPracticeSession).where(
            QbPracticeSession.user_id == user_id
        ))

        r.mastery_count = await _exec(db, delete(QbUserQuestionMastery).where(
            QbUserQuestionMastery.user_id == user_id
        ))
        r.knowledge_mastery_count = await _exec(
            db,
            delete(QbUserKnowledgeMastery).where(QbUserKnowledgeMastery.user_id == user_id),
        )
        r.bank_progress_count = await _exec(db, delete(QbUserBankItemProgress).where(
            QbUserBankItemProgress.user_id == user_id
        ))
        r.practice_stats_count = await _exec(db, delete(QbUserPracticeStatistics).where(
            QbUserPracticeStatistics.user_id == user_id
        ))
        r.daily_stats_count = await _exec(db, delete(QbUserDailyStatistics).where(
            QbUserDailyStatistics.user_id == user_id
        ))

        await db.flush()
        return r


async def _exec(db: AsyncSession, stmt: object) -> int:
    result = await db.execute(stmt)
    return int(result.rowcount or 0)


practice_data_reset_service: PracticeDataResetService = PracticeDataResetService()
