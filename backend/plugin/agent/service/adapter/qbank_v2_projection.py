from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING, Any

from backend.app.question_bank_v2.crud.crud_evaluation import evaluation_run_dao
from backend.app.question_bank_v2.crud.crud_practice import (
    practice_response_dao,
    practice_session_dao,
    question_attempt_dao,
)
from backend.app.question_bank_v2.service.review_schedule_service import review_schedule_service
from backend.app.question_bank_v2.service.statistics_service import statistics_service
from backend.plugin.agent.crud import agent_run_dao
from backend.utils.timezone import timezone

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.plugin.agent.model import AgentRun


class QbankV2ProjectionService:
    """将申论 Agent 终态结果投影回题库 V2。"""

    @staticmethod
    def _score(result: dict[str, Any], max_score: Decimal) -> Decimal | None:
        """读取展示分并限制到本次题目满分。"""
        value = result.get('display_score')
        if value is None:
            return None
        try:
            score = Decimal(str(value)).quantize(Decimal('0.01'))
        except (InvalidOperation, TypeError, ValueError):
            return None
        return min(max(score, Decimal(0)), max_score)

    @staticmethod
    def _is_correct(*, score: Decimal, max_score: Decimal) -> bool:
        """按申论批改的百分制阈值映射题库二值掌握结果。"""
        return max_score > 0 and score >= max_score * Decimal('0.60')

    @staticmethod
    def _projection_state(attempt: Any) -> dict[str, Any]:
        result = dict(attempt.grading_result or {})
        projection = result.get('agent_projection')
        return dict(projection) if isinstance(projection, dict) else {}

    async def project_success(  # noqa: C901
        self,
        *,
        db: AsyncSession,
        run: AgentRun,
        attempt_id: int,
        user_id: int,
        result: dict[str, Any],
    ) -> bool:
        """
        将一次成功批改幂等地写回题库作答、答题卡、统计和会话聚合。

        只有当前 Agent 运行仍是该作答的最新投影时，才会触发延迟评分统计。
        """
        context = await evaluation_run_dao.get_attempt_context(
            db,
            attempt_id=attempt_id,
            user_id=user_id,
            for_update=True,
        )
        if context is None:
            return False
        attempt = context.attempt
        previous = self._projection_state(attempt)
        score_status = str(result.get('score_status') or result.get('status') or '').lower()
        if previous.get('status') == 'graded':
            return await self._refresh_graded_projection(
                db=db,
                run=run,
                context=context,
                previous=previous,
                result=result,
                score_status=score_status,
            )
        if attempt.grading_status == 'graded' and not previous:
            run.result_payload = {
                **dict(run.result_payload or {}),
                'qbank_projection': {
                    'status': 'already_graded',
                    'attempt_id': attempt.id,
                    'source_agent_run_id': None,
                },
            }
            await db.flush()
            return False
        if previous.get('agent_run_id') == run.id and previous.get('status') == 'review_required':
            return False

        if score_status not in {'valid', 'provisional'}:
            return False

        if score_status == 'provisional':
            attempt.grading_status = 'review_required'
            attempt.grading_method = 'ai'
            attempt.grading_result = {
                **dict(attempt.grading_result or {}),
                'agent_run_id': run.id,
                'agent_projection': {'agent_run_id': run.id, 'status': 'review_required'},
            }
            if await question_attempt_dao.is_latest_for_item(db, attempt):
                response = await practice_response_dao.get(
                    db,
                    session_id=context.session.id,
                    session_item_id=context.session_item.id,
                    for_update=True,
                )
                if response is not None:
                    response.status = 'review_required'
                    response.grading_status = 'review_required'
                    response.is_correct = None
                    response.score = None
                    response.graded_time = None
            run.result_payload = {
                **dict(run.result_payload or {}),
                'qbank_projection': {'status': 'review_required', 'attempt_id': attempt.id},
            }
            await db.flush()
            return False

        score = self._score(result, context.session_item.max_score)
        if score is None:
            return False
        is_correct = self._is_correct(score=score, max_score=context.session_item.max_score)
        attempt.is_correct = is_correct
        attempt.score = score
        attempt.grading_status = 'graded'
        attempt.grading_method = 'ai'
        attempt.grading_result = {
            **dict(attempt.grading_result or {}),
            'agent_run_id': run.id,
            'agent_score_status': score_status,
            'agent_display_score': str(score),
            'agent_projection': {'agent_run_id': run.id, 'status': 'graded'},
        }
        await review_schedule_service.apply_delayed_grade(
            db=db,
            attempt=attempt,
            session_item=context.session_item,
        )
        await statistics_service.apply_delayed_grade(
            db=db,
            attempt=attempt,
            max_score=context.session_item.max_score,
        )
        if await question_attempt_dao.is_latest_for_item(db, attempt):
            response = await practice_response_dao.get(
                db,
                session_id=context.session.id,
                session_item_id=context.session_item.id,
                for_update=True,
            )
            if response is not None:
                response.status = 'graded'
                response.grading_status = 'graded'
                response.is_correct = is_correct
                response.score = score
                response.graded_time = timezone.now()
        await db.flush()
        await practice_session_dao.refresh_aggregates(db, context.session)
        run.result_payload = {
            **dict(run.result_payload or {}),
            'qbank_projection': {
                'status': 'graded',
                'attempt_id': attempt.id,
                'score': str(score),
                'is_correct': is_correct,
            },
        }
        await db.flush()
        return True

    async def _refresh_graded_projection(
        self,
        *,
        db: AsyncSession,
        run: AgentRun,
        context: Any,
        previous: dict[str, Any],
        result: dict[str, Any],
        score_status: str,
    ) -> bool:
        """更新强制重批结果指针，但不重复累计掌握度和统计。"""
        attempt = context.attempt
        previous_run_id = int(previous.get('agent_run_id') or 0)
        if previous_run_id >= run.id or score_status != 'valid':
            run.result_payload = {
                **dict(run.result_payload or {}),
                'qbank_projection': {
                    'status': 'superseded' if previous_run_id > run.id else 'already_graded',
                    'attempt_id': attempt.id,
                    'source_agent_run_id': previous_run_id or None,
                },
            }
            await db.flush()
            return False
        score = self._score(result, context.session_item.max_score)
        if score is None:
            return False
        is_correct = self._is_correct(score=score, max_score=context.session_item.max_score)
        attempt.is_correct = is_correct
        attempt.score = score
        attempt.grading_status = 'graded'
        attempt.grading_method = 'ai'
        attempt.grading_result = {
            **dict(attempt.grading_result or {}),
            'agent_run_id': run.id,
            'agent_score_status': score_status,
            'agent_display_score': str(score),
            'agent_projection': {'agent_run_id': run.id, 'status': 'graded'},
        }
        if await question_attempt_dao.is_latest_for_item(db, attempt):
            response = await practice_response_dao.get(
                db,
                session_id=context.session.id,
                session_item_id=context.session_item.id,
                for_update=True,
            )
            if response is not None:
                response.status = 'graded'
                response.grading_status = 'graded'
                response.is_correct = is_correct
                response.score = score
                response.graded_time = timezone.now()
        run.result_payload = {
            **dict(run.result_payload or {}),
            'qbank_projection': {
                'status': 'regraded',
                'attempt_id': attempt.id,
                'previous_agent_run_id': previous_run_id,
                'score': str(score),
                'is_correct': is_correct,
            },
        }
        await db.flush()
        return True

    async def replay_run(self, *, db: AsyncSession, run_id: int, user_id: int) -> bool:
        """对历史成功运行补做题库投影。"""
        run = await agent_run_dao.get_owned(db, run_id=run_id, user_id=user_id)
        if run is None:
            raise ValueError('Agent 运行不存在')
        if run.agent_key != 'shenlun.grading' or run.subject_type != 'qbank_v2_attempt':
            raise ValueError('Agent 运行不是申论作答批改')
        if run.status != 'succeeded' or not isinstance(run.result_payload, dict):
            raise ValueError('只有带有效结果的成功运行可以补投影')
        return await self.project_success(
            db=db,
            run=run,
            attempt_id=run.subject_id,
            user_id=user_id,
            result=run.result_payload,
        )


qbank_v2_projection_service = QbankV2ProjectionService()
