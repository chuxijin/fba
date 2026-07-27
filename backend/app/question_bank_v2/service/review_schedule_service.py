from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from importlib.metadata import version

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.crud.crud_review import (
    user_question_mastery_dao,
    wrong_question_state_dao,
)
from backend.app.question_bank_v2.model.practice import QbPracticeSessionItem, QbQuestionAttempt
from backend.app.question_bank_v2.model.statistics import QbUserQuestionMastery
from backend.common.fsrs import NEW_CARD_STATE, ReviewForecast, ReviewResult, fsrs_engine

FSRS_VERSION = version('fsrs')


@dataclass(slots=True)
class MasteryFSRSRecord:
    """将题目掌握度中的算法私有状态适配为通用 FSRS 协议"""

    state: int
    step: int | None
    stability: float | None
    difficulty: float | None
    due: datetime | None
    last_review: datetime | None


class ReviewScheduleService:
    """用户题目掌握度和 FSRS 调度服务类"""

    @staticmethod
    def _algorithm_state(*, mastery: QbUserQuestionMastery) -> dict:
        """获取有稳定默认值的 FSRS 私有状态"""
        state = mastery.algorithm_state or {}
        return {
            'state': int(state.get('state', NEW_CARD_STATE)),
            'step': state.get('step', 0),
            'stability': state.get('stability'),
            'difficulty': state.get('difficulty'),
        }

    @staticmethod
    def _to_record(*, mastery: QbUserQuestionMastery) -> MasteryFSRSRecord:
        """构建通用 FSRS 输入记录"""
        state = ReviewScheduleService._algorithm_state(mastery=mastery)
        return MasteryFSRSRecord(
            **state,
            due=mastery.next_review_time,
            last_review=mastery.last_review_time,
        )

    @staticmethod
    def _mastery_score(*, current: Decimal, rating: int) -> Decimal:
        """使用平滑后的四级评分维护 0-1 掌握度展示值"""
        rating_score = Decimal(rating - 1) / Decimal(3)
        return (current * Decimal('0.7') + rating_score * Decimal('0.3')).quantize(Decimal('0.0001'))

    @staticmethod
    def forecast(*, mastery: QbUserQuestionMastery) -> ReviewForecast:
        """预览当前调度状态下四种评分的下次复习时间"""
        return fsrs_engine.forecast(ReviewScheduleService._to_record(mastery=mastery))

    @staticmethod
    async def ensure_mastery(
        *,
        db: AsyncSession,
        user_id: int,
        question_id: int,
        question_revision_id: int,
        now: datetime,
        for_update: bool = False,
    ) -> QbUserQuestionMastery:
        """按需创建题目掌握度和新 FSRS 卡片"""
        mastery = await user_question_mastery_dao.get_by_question(
            db,
            user_id=user_id,
            question_id=question_id,
            for_update=for_update,
        )
        if mastery is not None:
            mastery.last_question_revision_id = question_revision_id
            return mastery

        defaults = fsrs_engine.new_card_defaults(now)
        return await user_question_mastery_dao.create(
            db,
            {
                'user_id': user_id,
                'question_id': question_id,
                'last_question_revision_id': question_revision_id,
                'algorithm_name': 'fsrs',
                'algorithm_version': FSRS_VERSION,
                'algorithm_state': {
                    'state': defaults['state'],
                    'step': defaults['step'],
                    'stability': None,
                    'difficulty': None,
                },
                'state': 'learning',
                'next_review_time': defaults['due'],
            },
        )

    @staticmethod
    async def apply_attempt(
        *,
        db: AsyncSession,
        attempt: QbQuestionAttempt,
        session_item: QbPracticeSessionItem,
    ) -> None:
        """由不可变作答事实同步掌握度和错题当前状态"""
        mastery = await ReviewScheduleService.ensure_mastery(
            db=db,
            user_id=attempt.user_id,
            question_id=attempt.question_id,
            question_revision_id=attempt.question_revision_id,
            now=attempt.submitted_time,
            for_update=True,
        )
        mastery.attempt_count += 1
        mastery.correct_count += int(attempt.is_correct is True)
        mastery.last_attempt_time = attempt.submitted_time

        wrong_state = await wrong_question_state_dao.get_by_question(
            db,
            user_id=attempt.user_id,
            question_id=attempt.question_id,
            for_update=True,
        )
        if attempt.is_correct is False:
            if mastery.state in {'review', 'mastered'}:
                mastery.lapse_count += 1
            mastery.state = 'learning'
            if wrong_state is None:
                await wrong_question_state_dao.create(
                    db,
                    {
                        'user_id': attempt.user_id,
                        'question_id': attempt.question_id,
                        'last_question_revision_id': attempt.question_revision_id,
                        'source_attempt_id': attempt.id,
                        'source_bank_item_id': session_item.bank_item_id,
                        'entry_source': 'attempt',
                        'status': 'active',
                        'wrong_count': 1,
                        'first_wrong_time': attempt.submitted_time,
                        'last_wrong_time': attempt.submitted_time,
                        'last_practice_time': attempt.submitted_time,
                        'last_wrong_response': attempt.response_data,
                        'created_by': attempt.user_id,
                    },
                )
            else:
                wrong_state.last_question_revision_id = attempt.question_revision_id
                wrong_state.source_attempt_id = attempt.id
                wrong_state.source_bank_item_id = session_item.bank_item_id
                wrong_state.status = 'active'
                wrong_state.wrong_count += 1
                wrong_state.correct_streak = 0
                wrong_state.last_wrong_time = attempt.submitted_time
                wrong_state.last_practice_time = attempt.submitted_time
                wrong_state.last_wrong_response = attempt.response_data
        elif attempt.is_correct is True and wrong_state is not None:
            wrong_state.last_question_revision_id = attempt.question_revision_id
            wrong_state.correct_streak += 1
            wrong_state.last_practice_time = attempt.submitted_time
        await db.flush()

    @staticmethod
    async def schedule_review(
        *,
        db: AsyncSession,
        mastery: QbUserQuestionMastery,
        rating: int,
        reviewed_time: datetime,
    ) -> tuple[datetime | None, ReviewResult, ReviewForecast]:
        """推进一次 FSRS 复习并返回前后调度结果"""
        due_before = mastery.next_review_time
        before_state = ReviewScheduleService._algorithm_state(mastery=mastery)['state']
        update_data, result = fsrs_engine.schedule(
            ReviewScheduleService._to_record(mastery=mastery),
            rating,
            now=reviewed_time,
        )
        mastery.algorithm_name = 'fsrs'
        mastery.algorithm_version = FSRS_VERSION
        mastery.algorithm_state = {
            'state': update_data['state'],
            'step': update_data['step'],
            'stability': update_data['stability'],
            'difficulty': update_data['difficulty'],
        }
        mastery.state = 'review' if update_data['state'] == 2 else 'learning'
        mastery.mastery_score = ReviewScheduleService._mastery_score(
            current=mastery.mastery_score,
            rating=rating,
        )
        mastery.review_count += 1
        mastery.lapse_count += int(rating == 1 and before_state == 2)
        mastery.last_review_time = update_data['last_review']
        mastery.next_review_time = update_data['due']
        await db.flush()
        forecast = ReviewScheduleService.forecast(mastery=mastery)
        return due_before, result, forecast


review_schedule_service: ReviewScheduleService = ReviewScheduleService()
