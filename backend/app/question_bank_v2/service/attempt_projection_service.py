"""作答投影的事务内凭据。调用方先锁用户、会话，再按ID升序锁全部涉及题目。"""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.model.practice import QbPracticeSessionItem, QbQuestionAttempt
from backend.app.question_bank_v2.model.question import QbQuestion
from backend.app.question_bank_v2.service.review_schedule_service import review_schedule_service
from backend.app.question_bank_v2.service.statistics_service import statistics_service
from backend.app.question_bank_v2.utils.external_practice import is_external_practice


class AttemptProjectionService:
    @staticmethod
    async def lock_questions(db: AsyncSession, question_ids: Sequence[int]) -> None:
        # 一卷多个题目必须在第一次更新统计之前全部升序加锁，避免两卷交叉题序死锁。
        for question_id in sorted(set(question_ids)):
            await db.execute(select(QbQuestion.id).where(QbQuestion.id == question_id).with_for_update())

    @staticmethod
    async def apply(
        *,
        db: AsyncSession,
        attempt: QbQuestionAttempt,
        session_item: QbPracticeSessionItem,
        resolve_threshold: int = 3,
        delayed: bool = False,
    ) -> None:
        if is_external_practice(attempt.grading_result):
            return
        await AttemptProjectionService.lock_questions(db, [attempt.question_id])
        details = dict(attempt.grading_result or {})
        marker = dict(details.get('_projection') or {})
        # 上线前的普通练习/已结算考试已写过基数。仅在延迟判分路径兼容，绝不盲目重放历史。
        if delayed and '_submission' not in details and not marker:
            marker = {'submitted': True, 'graded': False}
        if not marker.get('submitted'):
            await review_schedule_service.apply_attempt(
                db=db, attempt=attempt, session_item=session_item, resolve_threshold=resolve_threshold
            )
            await statistics_service.apply_attempt(db=db, attempt=attempt, max_score=session_item.max_score)
            marker = {'submitted': True, 'graded': attempt.is_correct is not None}
        elif delayed and attempt.is_correct is not None and not marker.get('graded'):
            await review_schedule_service.apply_delayed_grade(db=db, attempt=attempt, session_item=session_item)
            await statistics_service.apply_delayed_grade(db=db, attempt=attempt, max_score=session_item.max_score)
            marker['graded'] = True
        details = {**details, **(attempt.grading_result or {})}
        details['_projection'] = marker
        attempt.grading_result = details
        await db.flush()


attempt_projection_service = AttemptProjectionService()
