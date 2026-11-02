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
from backend.app.question_bank_v2.schema.review import (
    ENTRY_METADATA_MODULE_PATH_KEY,
    ENTRY_METADATA_SECTION_KEY,
)
from backend.app.question_bank_v2.service.knowledge_mastery_service import knowledge_mastery_service
from backend.app.question_bank_v2.service.practice_schedule_service import (
    ALGORITHM,
    first_practice_time,
    schedule,
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
        """只使用同会话首次独立作答；重试/揭晓后的改答不制造记忆成功。"""
        if attempt.is_correct is None or getattr(attempt, 'attempt_no', 1) != 1 or wrong_state.status == 'suspended':
            return
        before = dict(getattr(wrong_state, 'fsrs_data', None) or {})
        last_review = before.get('last_review')
        if last_review and datetime.fromisoformat(last_review) > attempt.submitted_time:
            return  # 迟到的AI判分不能把较新的记忆状态倒退。
        if before.get('last_attempt_id') == attempt.id:
            return
        rating = 3 if attempt.is_correct else 1
        after, due = schedule(before, rating=rating, now=attempt.submitted_time)
        wrong_state.fsrs_data = {**after, 'last_attempt_id': attempt.id}
        wrong_state.last_rating = rating
        wrong_state.next_practice_time = due
        details = dict(getattr(attempt, 'grading_result', None) or {})
        details['_memory'] = {
            'algorithm': ALGORITHM,
            'before': before,
            'after': after,
            'rating': rating,
            'due': due.isoformat(),
            'confirmed': False,
        }
        attempt.grading_result = details
        wrong_state.last_duration_ms = attempt.duration_ms

    @staticmethod
    def _attempt_metadata(session_item: QbPracticeSessionItem) -> dict[str, object]:
        """从投递快照提取原试卷章节路径，供错题浏览按题型聚拢。"""
        raw_display = getattr(session_item, 'display_config', None)
        display = raw_display if isinstance(raw_display, dict) else {}
        external = display.get('external_practice') if isinstance(display.get('external_practice'), dict) else {}
        raw_path = external.get('module_path')
        module_path = [str(item) for item in raw_path if str(item).strip()] if isinstance(raw_path, list) else []
        section_name = str(display.get('section_name') or (module_path[0] if module_path else '')).strip()
        metadata: dict[str, object] = {}
        if section_name:
            metadata[ENTRY_METADATA_SECTION_KEY] = section_name
        if module_path:
            metadata[ENTRY_METADATA_MODULE_PATH_KEY] = module_path
        return metadata

    @staticmethod
    def _merge_attempt_metadata(
        wrong_state: QbWrongQuestionState,
        session_item: QbPracticeSessionItem,
    ) -> None:
        """只补缺失的章节路径，保留错题最初导入时的归属。"""
        raw_metadata = getattr(wrong_state, 'entry_metadata', None)
        metadata = dict(raw_metadata) if isinstance(raw_metadata, dict) else {}
        changed = False
        for key, value in ReviewScheduleService._attempt_metadata(session_item).items():
            if value and not metadata.get(key):
                metadata[key] = value
                changed = True
        if changed:
            wrong_state.entry_metadata = metadata

    @staticmethod
    def _has_newer_memory(wrong_state: QbWrongQuestionState, now: datetime) -> bool:
        last_review = (wrong_state.fsrs_data or {}).get('last_review')
        return bool(last_review and datetime.fromisoformat(last_review) > now)

    @staticmethod
    def _update_wrong_bank_context(wrong_state: QbWrongQuestionState, session_item: QbPracticeSessionItem) -> None:
        if session_item.bank_item_id is not None:
            wrong_state.source_bank_item_id = session_item.bank_item_id

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
        if wrong_state is not None:
            ReviewScheduleService._merge_attempt_metadata(wrong_state, session_item)
            if ReviewScheduleService._has_newer_memory(wrong_state, now):
                return  # 迟到判分保留全局统计，但不能覆盖较新错题状态和最近练习时间。
        # 背题/旧卷回看不是独立回忆；不可用其“已看”提交推进FSRS。
        if isinstance(attempt.response_data, dict) and attempt.response_data.get('mode') == 'memorize':
            return

        if attempt.is_correct is False:
            mastery.state = 'learning'
            if wrong_state is None:
                wrong_state = await wrong_question_state_dao.create(
                    db,
                    {
                        'user_id': attempt.user_id,
                        'question_id': attempt.question_id,
                        'source_attempt_id': attempt.id,
                        'source_bank_item_id': session_item.bank_item_id,
                        'entry_source': 'attempt',
                        'entry_metadata': ReviewScheduleService._attempt_metadata(session_item),
                        'status': 'active',
                        'wrong_count': 1,
                        'first_wrong_time': now,
                        'last_wrong_time': now,
                        'last_practice_time': now,
                        'last_wrong_response': attempt.response_data,
                        'last_duration_ms': attempt.duration_ms,
                        'next_practice_time': first_practice_time(now),
                        'created_by': attempt.user_id,
                    },
                )
                # 首次答错是失败证据，但第一轮延迟验证采用次日启动规则。
                ReviewScheduleService._advance_schedule(wrong_state=wrong_state, attempt=attempt)
                wrong_state.next_practice_time = first_practice_time(now)
                if (attempt.grading_result or {}).get('_memory'):
                    attempt.grading_result = {
                        **attempt.grading_result,
                        '_memory': {
                            **attempt.grading_result['_memory'],
                            'due': wrong_state.next_practice_time.isoformat(),
                        },
                    }
                return
            was_suspended = wrong_state.status == 'suspended'
            wrong_state.resolved_time = None
            wrong_state.wrong_count += 1
            wrong_state.correct_streak = 0
            wrong_state.source_attempt_id = attempt.id
            ReviewScheduleService._update_wrong_bank_context(wrong_state, session_item)
            wrong_state.last_wrong_time = now
            wrong_state.last_practice_time = now
            wrong_state.last_wrong_response = attempt.response_data
            if not was_suspended:
                wrong_state.status = 'active'
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
        await knowledge_mastery_service.apply_attempt(
            db,
            attempt=attempt,
            session_item=session_item,
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
        await knowledge_mastery_service.apply_delayed_grade(
            db,
            attempt=attempt,
            session_item=session_item,
        )
        await db.flush()

    @staticmethod
    def reschedule(*, wrong_state: QbWrongQuestionState, now: datetime) -> None:
        """恢复仅重新开放队列，不虚构FSRS反馈。"""
        wrong_state.next_practice_time = first_practice_time(now)


review_schedule_service: ReviewScheduleService = ReviewScheduleService()
