from datetime import datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.crud.crud_review import (
    user_question_mastery_dao,
    wrong_question_state_dao,
)
from backend.app.question_bank_v2.crud.crud_statistics import user_bank_item_progress_dao
from backend.app.question_bank_v2.model.practice import QbPracticeSessionItem, QbQuestionAttempt
from backend.app.question_bank_v2.model.review import QbWrongQuestionState
from backend.app.question_bank_v2.model.statistics import QbUserQuestionMastery
from backend.app.question_bank_v2.service.practice_schedule_service import (
    derive_rating,
    next_practice_level,
    next_practice_time,
)

DEFAULT_RESOLVE_THRESHOLD = 3


class ReviewScheduleService:
    """由不可变作答事实维护掌握度、错题本状态和重练调度"""

    @staticmethod
    async def ensure_mastery(
        *,
        db: AsyncSession,
        user_id: int,
        question_id: int,
        for_update: bool = False,
    ) -> QbUserQuestionMastery:
        """按需创建题目掌握度"""
        mastery = await user_question_mastery_dao.get_by_question(
            db,
            user_id=user_id,
            question_id=question_id,
            for_update=for_update,
        )
        if mastery is not None:
            return mastery
        return await user_question_mastery_dao.create(
            db,
            {'user_id': user_id, 'question_id': question_id, 'state': 'learning'},
        )

    @staticmethod
    def _refresh_mastery_score(*, mastery: QbUserQuestionMastery) -> None:
        """由累计正确率维护 0-1 掌握度展示值"""
        if mastery.attempt_count <= 0:
            return
        mastery.mastery_score = (Decimal(mastery.correct_count) / Decimal(mastery.attempt_count)).quantize(
            Decimal('0.0001')
        )

    @staticmethod
    def _advance_schedule(*, wrong_state: QbWrongQuestionState, attempt: QbQuestionAttempt) -> None:
        """按客观派生等级推进重练阶梯"""
        rating = derive_rating(
            is_correct=attempt.is_correct,
            duration_ms=attempt.duration_ms,
            baseline_ms=wrong_state.last_duration_ms,
        )
        if rating is not None:
            wrong_state.last_rating = rating
            wrong_state.practice_level = next_practice_level(level=wrong_state.practice_level, rating=rating)
            wrong_state.next_practice_time = next_practice_time(
                level=wrong_state.practice_level,
                now=attempt.submitted_time,
            )
        wrong_state.last_duration_ms = attempt.duration_ms

    @staticmethod
    async def _sync_wrong_state(
        *,
        db: AsyncSession,
        attempt: QbQuestionAttempt,
        session_item: QbPracticeSessionItem,
        mastery: QbUserQuestionMastery,
        resolve_threshold: int,
    ) -> None:
        """由作答事实推进错题本状态与重练调度"""
        wrong_state = await wrong_question_state_dao.get_by_question(
            db,
            user_id=attempt.user_id,
            question_id=attempt.question_id,
            for_update=True,
        )
        now = attempt.submitted_time

        if attempt.is_correct is False:
            mastery.state = 'learning'
            if wrong_state is None:
                await wrong_question_state_dao.create(
                    db,
                    {
                        'user_id': attempt.user_id,
                        'question_id': attempt.question_id,
                        'source_attempt_id': attempt.id,
                        'source_bank_item_id': session_item.bank_item_id,
                        'entry_source': 'attempt',
                        'status': 'active',
                        'wrong_count': 1,
                        'first_wrong_time': now,
                        'last_wrong_time': now,
                        'last_practice_time': now,
                        'last_wrong_response': attempt.response_data,
                        'last_duration_ms': attempt.duration_ms,
                        'next_practice_time': next_practice_time(level=0, now=now),
                        'created_by': attempt.user_id,
                    },
                )
                return
            wrong_state.status = 'active'
            wrong_state.resolved_time = None
            wrong_state.wrong_count += 1
            wrong_state.correct_streak = 0
            wrong_state.source_attempt_id = attempt.id
            if session_item.bank_item_id is not None:
                wrong_state.source_bank_item_id = session_item.bank_item_id
            wrong_state.last_wrong_time = now
            wrong_state.last_practice_time = now
            wrong_state.last_wrong_response = attempt.response_data
            ReviewScheduleService._advance_schedule(wrong_state=wrong_state, attempt=attempt)
            return

        if attempt.is_correct is True and wrong_state is not None:
            wrong_state.correct_streak += 1
            wrong_state.last_practice_time = now
            ReviewScheduleService._advance_schedule(wrong_state=wrong_state, attempt=attempt)
            # 复盘过的题已经想清楚错因，做对一次即可移出；未复盘的仍需连对到偏好阈值
            threshold = 1 if wrong_state.review_count > 0 else resolve_threshold
            if wrong_state.status == 'active' and wrong_state.correct_streak >= threshold:
                wrong_state.status = 'resolved'
                wrong_state.resolved_time = now
                wrong_state.next_practice_time = None
                mastery.state = 'mastered'

    @staticmethod
    async def apply_attempt(
        *,
        db: AsyncSession,
        attempt: QbQuestionAttempt,
        session_item: QbPracticeSessionItem,
        resolve_threshold: int = DEFAULT_RESOLVE_THRESHOLD,
    ) -> None:
        """由不可变作答事实同步掌握度和错题当前状态"""
        mastery = await ReviewScheduleService.ensure_mastery(
            db=db,
            user_id=attempt.user_id,
            question_id=attempt.question_id,
            for_update=True,
        )
        mastery.attempt_count += 1
        mastery.correct_count += int(attempt.is_correct is True)
        mastery.last_attempt_time = attempt.submitted_time
        ReviewScheduleService._refresh_mastery_score(mastery=mastery)
        await user_bank_item_progress_dao.apply_attempt(
            db,
            attempt=attempt,
            bank_item_id=session_item.bank_item_id,
        )
        await ReviewScheduleService._sync_wrong_state(
            db=db,
            attempt=attempt,
            session_item=session_item,
            mastery=mastery,
            resolve_threshold=resolve_threshold,
        )
        await db.flush()

    @staticmethod
    async def apply_delayed_grade(
        *,
        db: AsyncSession,
        attempt: QbQuestionAttempt,
        session_item: QbPracticeSessionItem,
        resolve_threshold: int = DEFAULT_RESOLVE_THRESHOLD,
    ) -> None:
        """为已累计提交次数的主观题补写掌握度、题项进度和错题状态"""
        mastery = await ReviewScheduleService.ensure_mastery(
            db=db,
            user_id=attempt.user_id,
            question_id=attempt.question_id,
            for_update=True,
        )
        mastery.correct_count += int(attempt.is_correct is True)
        ReviewScheduleService._refresh_mastery_score(mastery=mastery)
        await user_bank_item_progress_dao.apply_delayed_grade(
            db,
            attempt=attempt,
            bank_item_id=session_item.bank_item_id,
        )
        await ReviewScheduleService._sync_wrong_state(
            db=db,
            attempt=attempt,
            session_item=session_item,
            mastery=mastery,
            resolve_threshold=resolve_threshold,
        )
        await db.flush()

    @staticmethod
    def reschedule(*, wrong_state: QbWrongQuestionState, now: datetime) -> None:
        """手动恢复错题时按当前阶梯重新排期"""
        wrong_state.next_practice_time = next_practice_time(level=wrong_state.practice_level, now=now)


review_schedule_service: ReviewScheduleService = ReviewScheduleService()
