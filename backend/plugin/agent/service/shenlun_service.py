from __future__ import annotations

import asyncio
import hashlib

from datetime import timedelta
from typing import TYPE_CHECKING
from uuid import uuid4

from backend.common.exception import errors
from backend.core.conf import settings
from backend.plugin.agent.crud import agent_grading_feedback_dao, agent_run_dao
from backend.plugin.agent.schema.grading import (
    AgentRunStepRead,
    GradingFeedbackParam,
    GradingRunRead,
    StartShenlunGradingParam,
    StartShenlunGradingResult,
)
from backend.plugin.agent.service.access.quota import agent_quota_service
from backend.plugin.agent.service.adapter.qbank_v2_adapter import qbank_v2_adapter
from backend.plugin.agent.service.adapter.qbank_v2_projection import qbank_v2_projection_service
from backend.plugin.agent.service.runtime.events import agent_event_bus
from backend.plugin.agent.service.shenlun.answer_formatting import normalize_revised_answer_word_count
from backend.plugin.agent.service.shenlun.calibration_service import shenlun_calibration_service
from backend.plugin.agent.service.shenlun.common import infer_question_type
from backend.plugin.agent.service.shenlun.evidence_resolution import resolve_answer_evidence
from backend.plugin.agent.service.shenlun.pipeline import shenlun_grading_pipeline
from backend.plugin.agent.service.shenlun.report import render_grading_report
from backend.plugin.agent.service.shenlun.retrieval import shenlun_history_retriever
from backend.plugin.agent.service.shenlun.similar import shenlun_similar_question_retriever
from backend.utils.timezone import timezone

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.plugin.agent.model import AgentRun


class ShenlunGradingService:
    """申论批改 Agent 服务"""

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[None]] = set()
        self._semaphore: asyncio.Semaphore | None = None

    async def start(
        self,
        *,
        db: AsyncSession,
        attempt_id: int,
        user_id: int,
        params: StartShenlunGradingParam,
    ) -> StartShenlunGradingResult:
        idempotency_key = self._idempotency_key(
            user_id=user_id,
            attempt_id=attempt_id,
            force_regenerate=params.force_regenerate,
        )
        if not params.force_regenerate:
            existing = await agent_run_dao.get_by_idempotency(db, key=idempotency_key)
            if existing is not None:
                return self._start_result(existing.id, existing.status)

        input_data = await qbank_v2_adapter.get_attempt_input(db=db, attempt_id=attempt_id, user_id=user_id)
        await agent_quota_service.ensure_shenlun_grading(db=db, user_id=user_id)

        run = await agent_run_dao.create_run(
            db,
            data={
                'agent_key': 'shenlun.grading',
                'agent_version': '0.6.0',
                'workflow_key': 'shenlun-grading',
                'workflow_version': getattr(settings, 'AGENT_SHENLUN_WORKFLOW_VERSION', 'shenlun-grading-v5'),
                'user_id': user_id,
                'subject_type': 'qbank_v2_attempt',
                'subject_id': attempt_id,
                'idempotency_key': idempotency_key,
                'status': 'queued',
                'input_snapshot': {
                    'attempt_id': attempt_id,
                    'question_id': input_data.context.question.id,
                    'question_type': input_data.context.question.question_type,
                    'answer_hash': hashlib.sha256(input_data.answer_text.encode()).hexdigest(),
                    'answer_text': input_data.answer_text,
                },
                'config_snapshot': params.model_dump(mode='json'),
            },
        )
        await db.commit()
        self._schedule(run.id, user_id=user_id, attempt_id=attempt_id)
        return self._start_result(run.id, run.status)

    async def retry(self, *, db: AsyncSession, run_id: int, user_id: int) -> StartShenlunGradingResult:
        run = await agent_run_dao.get_owned(db, run_id=run_id, user_id=user_id)
        if run is None:
            raise errors.NotFoundError(msg='Agent 运行不存在')
        if run.status not in {'failed', 'cancelled'}:
            raise errors.ConflictError(msg='只有失败或已取消的运行可以重试，请使用强制重新批改生成新运行')
        if agent_quota_service.get_state(run.config_snapshot).get('status') in {'acquired', 'refund_pending'}:
            await self._refund_quota(db=db, run=run)
            await db.commit()
        await agent_quota_service.ensure_shenlun_grading(db=db, user_id=user_id)
        input_data = await qbank_v2_adapter.get_attempt_input(db=db, attempt_id=run.subject_id, user_id=user_id)
        retry = await agent_run_dao.create_run(
            db,
            data={
                'agent_key': run.agent_key,
                'agent_version': run.agent_version,
                'workflow_key': run.workflow_key,
                'workflow_version': run.workflow_version,
                'user_id': user_id,
                'subject_type': run.subject_type,
                'subject_id': run.subject_id,
                'idempotency_key': f'{run.idempotency_key}:retry:{uuid4().hex}',
                'status': 'queued',
                'input_snapshot': run.input_snapshot,
                'config_snapshot': self._retry_config(run.config_snapshot),
            },
        )
        await db.commit()
        self._schedule(retry.id, user_id=user_id, attempt_id=input_data.context.attempt.id)
        return self._start_result(retry.id, retry.status)

    async def recover_pending_runs(self) -> int:
        """应用启动时恢复排队任务和服务重启前遗留的陈旧运行。"""
        from backend.database.db import async_db_session

        stale_seconds = max(60, int(getattr(settings, 'AGENT_SHENLUN_STALE_SECONDS', 900)))
        stale_before = timezone.now() - timedelta(seconds=stale_seconds)
        async with async_db_session() as db:
            runs = await agent_run_dao.list_recoverable(
                db,
                agent_key='shenlun.grading',
                stale_before=stale_before,
                limit=100,
            )
        for run in runs:
            self._schedule(run.id, user_id=run.user_id, attempt_id=run.subject_id)
        return len(runs)

    async def shutdown(self) -> None:
        """停止本进程任务；运行协程会将已认领任务放回恢复队列。"""
        tasks = tuple(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def get_detail(self, *, db: AsyncSession, run_id: int, user_id: int) -> GradingRunRead:
        run = await agent_run_dao.get_owned(db, run_id=run_id, user_id=user_id)
        if run is None:
            raise errors.NotFoundError(msg='Agent 运行不存在')
        steps = await agent_run_dao.list_steps(db, run_id=run.id)
        return GradingRunRead(
            id=run.id,
            agent_key=run.agent_key,
            agent_version=run.agent_version,
            workflow_key=run.workflow_key,
            workflow_version=run.workflow_version,
            subject_type=run.subject_type,
            subject_id=run.subject_id,
            status=run.status,
            stage=run.stage,
            progress=run.progress,
            result_summary=run.result_summary,
            result_payload=run.result_payload,
            steps=[
                AgentRunStepRead(
                    step_no=step.step_no,
                    node_key=step.node_key,
                    status=step.status,
                    output_snapshot=step.output_snapshot,
                    duration_ms=step.duration_ms,
                )
                for step in steps
            ],
            error_code=run.error_code,
            error_message=run.error_message,
            started_time=run.started_time,
            finished_time=run.finished_time,
        )

    async def apply_feedback(
        self,
        *,
        db: AsyncSession,
        run_id: int,
        user_id: int,
        params: GradingFeedbackParam,
    ) -> GradingRunRead:
        """应用人工采分点纠正并重算结构化结果"""
        run = await agent_run_dao.get_owned(db, run_id=run_id, user_id=user_id)
        if run is None:
            raise errors.NotFoundError(msg='Agent 运行不存在')
        if params.corrected_status not in {'hit', 'partial', 'miss'}:
            raise errors.RequestError(msg='纠正状态必须是 hit、partial 或 miss')
        if params.scope not in {'report', 'question'}:
            raise errors.RequestError(msg='纠正范围必须是 report 或 question')
        result = dict(run.result_payload or {})
        answer_text = str((run.input_snapshot or {}).get('answer_text') or '')
        if params.corrected_status in {'hit', 'partial'} and (
            not params.corrected_quote or params.corrected_quote not in answer_text
        ):
            raise errors.RequestError(msg='命中或部分命中时，纠正引用必须来自答案原文')
        found = False
        for match in result.get('point_matches') or []:
            if match.get('point_key') != params.point_key:
                continue
            found = True
            before_snapshot = dict(match)
            match['status'] = params.corrected_status
            match['coverage_ratio'] = (
                1.0 if params.corrected_status == 'hit' else 0.5 if params.corrected_status == 'partial' else 0.0
            )
            match['answer_quote'] = params.corrected_quote if params.corrected_status != 'miss' else ''
            resolution = (
                resolve_answer_evidence(params.corrected_quote, answer_text)
                if params.corrected_status in {'hit', 'partial'}
                else {'status': 'not_required', 'spans': []}
            )
            match['evidence_status'] = resolution['status']
            match['evidence_spans'] = resolution.get('spans') or []
            match['feedback_applied'] = True
            match['feedback_note'] = params.note
            after_snapshot = dict(match)
            break
        if not found:
            raise errors.NotFoundError(msg='指定采分点不存在')
        result['score_status'] = 'stale'
        result['status'] = 'stale'
        result['feedback_applied'] = True
        result['feedback_note'] = params.note
        result.setdefault('quality_check', {})['passed'] = False
        result['quality_check']['notes'] = ['已应用人工采分点纠正，建议重新生成完整批改报告。']
        rubric = result.get('rubric') if isinstance(result.get('rubric'), dict) else {}
        if rubric:
            result['report_markdown'] = normalize_revised_answer_word_count(
                render_grading_report(result, rubric),
                str(result.get('word_limit') or rubric.get('word_limit') or ''),
            )
        question_id = int(rubric.get('question_id') or (run.input_snapshot or {}).get('question_id') or 0)
        await agent_grading_feedback_dao.upsert(
            db,
            data={
                'run_id': run.id,
                'user_id': user_id,
                'question_id': question_id,
                'point_key': params.point_key,
                'scope': params.scope,
                'corrected_status': params.corrected_status,
                'corrected_quote': params.corrected_quote,
                'note': params.note,
                'before_snapshot': before_snapshot,
                'after_snapshot': after_snapshot,
            },
        )
        if params.scope == 'question' and question_id:
            await agent_grading_feedback_dao.invalidate_question_rubrics(db, question_id=question_id)
        run.result_payload = result
        run.result_summary = f'{run.result_summary or result.get("overall_summary") or ""}（已应用人工纠正）'.strip()
        await db.commit()
        return await self.get_detail(db=db, run_id=run_id, user_id=user_id)

    def stream(self, run_id: int) -> AsyncIterator[str]:
        return agent_event_bus.stream(run_id)

    async def _run(self, run_id: int, *, user_id: int, attempt_id: int) -> None:
        from backend.database.db import async_db_session

        try:
            async with async_db_session() as db:
                run = await agent_run_dao.get_owned(db, run_id=run_id, user_id=user_id)
                if run is None:
                    return
                await self._acquire_quota(db=db, run=run)
                await agent_event_bus.publish(
                    run_id, {'run_id': run_id, 'status': run.status, 'stage': run.stage, 'progress': run.progress}
                )
                step_no = await agent_run_dao.next_step_no(db, run_id=run_id)
                payload = await qbank_v2_adapter.get_attempt_input(db=db, attempt_id=attempt_id, user_id=user_id)
                await agent_run_dao.add_step(
                    db,
                    data={
                        'run_id': run_id,
                        'step_no': step_no,
                        'node_key': 'context_loader',
                        'status': 'succeeded',
                        'input_snapshot': {'attempt_id': attempt_id},
                        'output_snapshot': {'recovered': step_no > 1},
                        'started_time': timezone.now(),
                        'finished_time': timezone.now(),
                    },
                )
                question_feedback = await agent_grading_feedback_dao.list_question_feedback(
                    db,
                    question_id=payload.context.question.id,
                )
                try:
                    history_evidence = await shenlun_history_retriever.retrieve(
                        db=db,
                        user_id=user_id,
                        question_id=payload.context.question.id,
                        question_type=payload.context.question.question_type,
                        current_attempt_id=attempt_id,
                    )
                except Exception as retrieval_error:
                    history_evidence = {
                        'history_attempt_count': 0,
                        'history_stable': False,
                        'retrieval_degraded': True,
                        'retrieval_error': str(retrieval_error)[:300],
                        'evidence': [],
                        'signals': [],
                    }
                run.stage = 'grading'
                run.progress = 0.4
                await db.commit()
                await agent_event_bus.publish(
                    run_id, {'run_id': run_id, 'status': run.status, 'stage': run.stage, 'progress': run.progress}
                )
                grading_started = timezone.now()

                question_type = infer_question_type(
                    payload.context.question.stem,
                    payload.reference_context,
                )
                similar_retrieval = await shenlun_similar_question_retriever.retrieve(
                    db=db,
                    question_id=payload.context.question.id,
                    question_text=payload.context.question.stem,
                    question_type=question_type,
                )
                similar_retrieval = await shenlun_similar_question_retriever.attach_rubric_precedents(
                    db=db,
                    retrieval=similar_retrieval,
                )

                result = await shenlun_grading_pipeline.run(
                    db=db,
                    payload={
                        'question_id': payload.context.question.id,
                        'question_type': payload.context.question.question_type,
                        'question': payload.context.question.stem,
                        'materials': payload.materials,
                        'reference_context': payload.reference_context,
                        'question_feedback': [
                            {
                                'point_key': item.point_key,
                                'corrected_status': item.corrected_status,
                                'corrected_quote': item.corrected_quote,
                                'note': item.note,
                            }
                            for item in question_feedback
                        ],
                        'history_evidence': history_evidence,
                        'similar_retrieval': similar_retrieval,
                        'calibration_policy': await shenlun_calibration_service.get_policy(
                            db=db,
                            bank_revision_id=payload.context.session.bank_revision_id,
                            question_type=question_type,
                        ),
                        'answer_text': payload.answer_text,
                        'max_score': str(payload.context.session_item.max_score),
                    },
                    model_name=(run.config_snapshot or {}).get('model_name'),
                )
                run.status = 'succeeded' if result.get('status') != 'fallback' else 'failed'
                run.stage = 'completed' if run.status == 'succeeded' else 'failed'
                run.progress = 1.0
                run.result_summary = (
                    (result.get('summary') or {}).get('verdict')
                    or result.get('overall_summary')
                    or '申论批改工作流已完成。'
                )
                run.result_payload = result
                run.finished_time = timezone.now()
                if run.status == 'succeeded':
                    await qbank_v2_projection_service.project_success(
                        db=db,
                        run=run,
                        attempt_id=attempt_id,
                        user_id=user_id,
                        result=result,
                    )
                    self._close_quota(run=run, status='consumed')
                else:
                    await self._refund_quota(db=db, run=run)
                pipeline_steps = result.get('pipeline_steps') or [
                    {
                        'node_key': 'shenlun_grading_pipeline',
                        'status': 'succeeded' if result.get('status') != 'fallback' else 'failed',
                    }
                ]
                model_name = (result.get('model') or {}).get('model_name')
                for pipeline_step in pipeline_steps:
                    await agent_run_dao.add_step(
                        db,
                        data={
                            'run_id': run_id,
                            'step_no': await agent_run_dao.next_step_no(db, run_id=run_id),
                            'node_key': pipeline_step.get('node_key') or 'shenlun_grading_pipeline',
                            'status': pipeline_step.get('status') or 'succeeded',
                            'input_snapshot': {
                                'question_type': payload.context.question.question_type,
                            },
                            'output_snapshot': {
                                'score': result.get('score') if pipeline_step.get('node_key') == 'validation' else None,
                                'display_score': result.get('display_score')
                                if pipeline_step.get('node_key') == 'validation'
                                else None,
                                'point_match_count': len(result.get('point_matches') or [])
                                if pipeline_step.get('node_key') in {'grading', 'validation'}
                                else None,
                                'duration_ms': pipeline_step.get('duration_ms', 0),
                            },
                            'model_name': model_name,
                            'duration_ms': int(pipeline_step.get('duration_ms') or 0),
                            'started_time': grading_started,
                            'finished_time': timezone.now(),
                        },
                    )
                await db.commit()
                try:
                    await shenlun_calibration_service.refresh(
                        db=db,
                        bank_revision_id=payload.context.session.bank_revision_id,
                        session_id=payload.context.session.id,
                    )
                except Exception:
                    await db.rollback()
                await agent_event_bus.publish(
                    run_id,
                    {
                        'run_id': run_id,
                        'status': run.status,
                        'stage': run.stage,
                        'progress': run.progress,
                        'result': result,
                    },
                )
        except Exception as exc:
            await self._handle_run_failure(run_id=run_id, user_id=user_id, exc=exc)
            await agent_event_bus.publish(
                run_id, {'run_id': run_id, 'status': 'failed', 'error_message': str(exc)[:500]}
            )

    async def _handle_run_failure(self, *, run_id: int, user_id: int, exc: Exception) -> None:
        """持久化最终失败状态，并尽力回滚已扣额度。"""
        from backend.database.db import async_db_session

        async with async_db_session() as db:
            run = await agent_run_dao.get_owned(db, run_id=run_id, user_id=user_id)
            if run is None:
                return
            refund_error: Exception | None = None
            try:
                await self._refund_quota(db=db, run=run)
            except Exception as quota_error:
                refund_error = quota_error
                await db.rollback()
                run = await agent_run_dao.get_owned(db, run_id=run_id, user_id=user_id)
                if run is None:
                    return
                self._close_quota(run=run, status='refund_pending', error=quota_error)
            run.status = 'failed'
            run.stage = 'failed'
            run.progress = 1.0
            run.error_code = type(exc).__name__
            run.error_message = str(exc)[:2000]
            if refund_error is not None:
                run.error_message = f'{run.error_message}\n额度退款待重试：{refund_error!s}'[:2000]
            run.finished_time = timezone.now()
            await agent_run_dao.add_step(
                db,
                data={
                    'run_id': run_id,
                    'step_no': await agent_run_dao.next_step_no(db, run_id=run_id),
                    'node_key': run.stage or 'shenlun_grading_pipeline',
                    'status': 'failed',
                    'input_snapshot': {},
                    'output_snapshot': None,
                    'error_message': str(exc)[:2000],
                    'started_time': run.started_time,
                    'finished_time': run.finished_time,
                },
            )
            await db.commit()

    def _schedule(self, run_id: int, *, user_id: int, attempt_id: int) -> None:
        task = asyncio.create_task(self._run_guarded(run_id, user_id=user_id, attempt_id=attempt_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run_guarded(self, run_id: int, *, user_id: int, attempt_id: int) -> None:
        limit = max(1, int(getattr(settings, 'AGENT_SHENLUN_MAX_CONCURRENCY', 2)))
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(limit)
        claimed = False
        heartbeat: asyncio.Task[None] | None = None
        try:
            async with self._semaphore:
                claimed = await self._claim(run_id=run_id, user_id=user_id)
                if not claimed:
                    return
                heartbeat = asyncio.create_task(self._heartbeat(run_id=run_id, user_id=user_id))
                await self._run(run_id, user_id=user_id, attempt_id=attempt_id)
        except asyncio.CancelledError:
            if claimed:
                await self._requeue_interrupted(run_id=run_id, user_id=user_id)
            raise
        finally:
            if heartbeat is not None:
                heartbeat.cancel()
                await asyncio.gather(heartbeat, return_exceptions=True)

    @staticmethod
    async def _claim(*, run_id: int, user_id: int) -> bool:
        from backend.database.db import async_db_session

        now = timezone.now()
        stale_before = now - timedelta(seconds=max(60, int(getattr(settings, 'AGENT_SHENLUN_STALE_SECONDS', 900))))
        async with async_db_session() as db:
            claimed = await agent_run_dao.claim_for_execution(
                db,
                run_id=run_id,
                user_id=user_id,
                stale_before=stale_before,
                started_time=now,
            )
            await db.commit()
            return claimed

    @staticmethod
    async def _heartbeat(*, run_id: int, user_id: int) -> None:
        from backend.database.db import async_db_session

        stale_seconds = max(60, int(getattr(settings, 'AGENT_SHENLUN_STALE_SECONDS', 900)))
        interval = max(15, stale_seconds // 3)
        while True:
            await asyncio.sleep(interval)
            async with async_db_session() as db:
                alive = await agent_run_dao.touch_running(db, run_id=run_id, user_id=user_id)
                await db.commit()
            if not alive:
                return

    @staticmethod
    async def _requeue_interrupted(*, run_id: int, user_id: int) -> None:
        from backend.database.db import async_db_session

        async with async_db_session() as db:
            await agent_run_dao.requeue_interrupted(db, run_id=run_id, user_id=user_id)
            await db.commit()

    @staticmethod
    async def _acquire_quota(*, db: AsyncSession, run: AgentRun) -> None:
        state = agent_quota_service.get_state(run.config_snapshot)
        if state.get('status') in {'acquired', 'consumed'}:
            return
        decision = await agent_quota_service.consume_shenlun_grading(
            db=db,
            user_id=run.user_id,
            run_id=run.id,
        )
        run.config_snapshot = agent_quota_service.set_state(
            run.config_snapshot,
            agent_quota_service.acquired_state(run_id=run.id, decision=decision),
        )
        await agent_run_dao.add_step(
            db,
            data={
                'run_id': run.id,
                'step_no': await agent_run_dao.next_step_no(db, run_id=run.id),
                'node_key': 'quota_access',
                'status': 'succeeded',
                'input_snapshot': {'profile_code': state.get('profile_code') or 'agent.shenlun.grade'},
                'output_snapshot': {
                    'reason_code': decision.reason_code,
                    'matched_grant': decision.matched_grant,
                    'consumed_ledger_id': decision.consumed_ledger_id,
                    'trial_mode': decision.trial_mode,
                },
                'started_time': timezone.now(),
                'finished_time': timezone.now(),
            },
        )
        await db.commit()

    @staticmethod
    async def _refund_quota(*, db: AsyncSession, run: AgentRun) -> None:
        state = agent_quota_service.get_state(run.config_snapshot)
        if state.get('status') not in {'acquired', 'refund_pending'}:
            return
        decision = agent_quota_service.restore_decision(state)
        if decision is None:
            ShenlunGradingService._close_quota(run=run, status='refund_pending')
            return
        await agent_quota_service.refund_shenlun_grading(
            db=db,
            user_id=run.user_id,
            run_id=run.id,
            decision=decision,
        )
        refundable_trial = bool(decision.trial_counter_key and decision.trial_idempotency_key)
        status = 'refunded' if decision.consumed_ledger_id is not None or refundable_trial else 'failed_unmetered'
        ShenlunGradingService._close_quota(run=run, status=status)

    @staticmethod
    def _close_quota(*, run: AgentRun, status: str, error: Exception | None = None) -> None:
        state = agent_quota_service.get_state(run.config_snapshot)
        if not state:
            return
        state['status'] = status
        if error is not None:
            state['error'] = str(error)[:500]
        run.config_snapshot = agent_quota_service.set_state(run.config_snapshot, state)

    @staticmethod
    def _retry_config(config_snapshot: dict[str, object] | None) -> dict[str, object]:
        config = dict(config_snapshot or {})
        config.pop('quota', None)
        return config

    @staticmethod
    def _idempotency_key(*, user_id: int, attempt_id: int, force_regenerate: bool) -> str:
        suffix = uuid4().hex if force_regenerate else 'latest'
        return f'shenlun.grading:{user_id}:{attempt_id}:{suffix}'

    @staticmethod
    def _start_result(run_id: int, status: str) -> StartShenlunGradingResult:
        return StartShenlunGradingResult(
            run_id=run_id,
            agent_key='shenlun.grading',
            status=status,
            stream_url=f'/api/v1/agent/shenlun/runs/{run_id}/stream',
        )


shenlun_grading_service = ShenlunGradingService()
