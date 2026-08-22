from __future__ import annotations

import asyncio
import hashlib
import json

from datetime import timedelta
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import select

from backend.app.question_bank_v2.model import QbQuestion, QbQuestionNote
from backend.common.exception import errors
from backend.core.conf import settings
from backend.plugin.agent.crud import (
    agent_run_dao,
    shenlun_coach_memory_dao,
    shenlun_coach_message_dao,
    shenlun_coach_session_dao,
    shenlun_training_plan_dao,
    shenlun_training_plan_item_dao,
)
from backend.plugin.agent.model import (
    AgentRun,
    ShenlunCoachMessage,
    ShenlunCoachSession,
    ShenlunTrainingPlan,
    ShenlunTrainingPlanItem,
)
from backend.plugin.agent.schema.coach import (
    CoachAnalyticsRead,
    CoachMemoryRead,
    CoachMessageParam,
    CoachRunRead,
    CoachRunStepRead,
    CoachSessionListRead,
    CoachSessionRead,
    GenerateTrainingPlanParam,
    StartCoachRunResult,
    TrainingPlanListRead,
    TrainingPlanRead,
)
from backend.plugin.agent.service.access.quota import agent_quota_service
from backend.plugin.agent.service.coach_intent import build_intent_plan
from backend.plugin.agent.service.coach_recommendation import coach_recommendation_service
from backend.plugin.agent.service.runtime.events import agent_event_bus
from backend.plugin.agent.service.runtime.model_resolver import resolve_agent_model
from backend.utils.timezone import timezone

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from sqlalchemy.ext.asyncio import AsyncSession


class ShenlunCoachService:
    """申论训练教练服务。"""

    def __init__(self) -> None:
        self._tasks: set[asyncio.Task[None]] = set()
        self._semaphore: asyncio.Semaphore | None = None

    async def start_message_run(
        self,
        *,
        db: AsyncSession,
        session_id: int,
        user_id: int,
        params: CoachMessageParam,
    ) -> StartCoachRunResult:
        session = await shenlun_coach_session_dao.get_owned_for_update(
            db,
            session_id=session_id,
            user_id=user_id,
        )
        if session is None:
            raise errors.NotFoundError(msg='教练会话不存在')
        if session.status != 'active':
            raise errors.ConflictError(msg='教练会话已归档')
        request_id = params.request_id or f'run-{uuid4().hex}'
        idempotency_key = f'shenlun.coach:{user_id}:{session_id}:{request_id}'
        existing = await agent_run_dao.get_by_idempotency(db, key=idempotency_key)
        if existing is not None:
            return self._start_run_result(existing.id, existing.status)
        run = await agent_run_dao.create_run(
            db,
            data={
                'agent_key': 'shenlun.coach',
                'agent_version': '0.2.0',
                'workflow_key': 'shenlun-coach',
                'workflow_version': 'shenlun-coach-v2',
                'user_id': user_id,
                'subject_type': 'shenlun_coach_session',
                'subject_id': session_id,
                'idempotency_key': idempotency_key,
                'status': 'queued',
                'stage': 'queued',
                'input_snapshot': {
                    'content': params.content.strip(),
                    'request_id': request_id,
                    'entrypoint': params.entrypoint,
                    'module': params.module,
                },
                'config_snapshot': {'model_name': params.model_name},
            },
        )
        await db.commit()
        self._schedule_message_run(run.id, user_id=user_id, session_id=session_id)
        return self._start_run_result(run.id, run.status)

    async def get_run(self, *, db: AsyncSession, run_id: int, user_id: int) -> CoachRunRead:
        run = await agent_run_dao.get_owned(db, run_id=run_id, user_id=user_id)
        if run is None or run.agent_key != 'shenlun.coach':
            raise errors.NotFoundError(msg='教练运行不存在')
        steps = await agent_run_dao.list_steps(db, run_id=run.id)
        return CoachRunRead(
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
                CoachRunStepRead(
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

    def stream(self, run_id: int) -> Any:
        return agent_event_bus.stream(run_id)

    async def recover_pending_runs(self) -> int:
        """应用启动时恢复排队或陈旧的教练运行。"""
        from backend.database.db import async_db_session

        stale_before = timezone.now() - timedelta(
            seconds=max(60, int(getattr(settings, 'AGENT_SHENLUN_STALE_SECONDS', 900)))
        )
        async with async_db_session() as db:
            runs = await agent_run_dao.list_recoverable(
                db,
                agent_key='shenlun.coach',
                stale_before=stale_before,
                limit=100,
            )
        for run in runs:
            self._schedule_message_run(run.id, user_id=run.user_id, session_id=run.subject_id)
        return len(runs)

    async def shutdown(self) -> None:
        tasks = tuple(self._tasks)
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    def _schedule_message_run(self, run_id: int, *, user_id: int, session_id: int) -> None:
        task = asyncio.create_task(self._run_message_guarded(run_id, user_id=user_id, session_id=session_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _run_message_guarded(self, run_id: int, *, user_id: int, session_id: int) -> None:
        from backend.database.db import async_db_session

        claimed = False
        heartbeat: asyncio.Task[None] | None = None
        try:
            limit = max(1, int(getattr(settings, 'AGENT_SHENLUN_MAX_CONCURRENCY', 2)))
            if self._semaphore is None:
                self._semaphore = asyncio.Semaphore(limit)
            async with self._semaphore:
                now = timezone.now()
                stale_before = now - timedelta(
                    seconds=max(60, int(getattr(settings, 'AGENT_SHENLUN_STALE_SECONDS', 900)))
                )
                async with async_db_session() as db:
                    claimed = await agent_run_dao.claim_for_execution(
                        db,
                        run_id=run_id,
                        user_id=user_id,
                        stale_before=stale_before,
                        started_time=now,
                    )
                    if not claimed:
                        return
                    await db.commit()
                heartbeat = asyncio.create_task(self._heartbeat(run_id=run_id, user_id=user_id))
                await self._run_message(run_id, user_id=user_id, session_id=session_id)
        except asyncio.CancelledError:
            if claimed:
                async with async_db_session() as db:
                    await agent_run_dao.requeue_interrupted(db, run_id=run_id, user_id=user_id)
                    await db.commit()
            raise
        finally:
            if heartbeat is not None:
                heartbeat.cancel()
                await asyncio.gather(heartbeat, return_exceptions=True)

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

    async def _run_message(self, run_id: int, *, user_id: int, session_id: int) -> None:
        from backend.database.db import async_db_session
        from backend.plugin.agent.schema.coach import CoachMessageParam

        async with async_db_session() as db:
            run = await agent_run_dao.get_owned(db, run_id=run_id, user_id=user_id)
            if run is None:
                return
            input_snapshot = run.input_snapshot or {}
            params = CoachMessageParam(
                content=str(input_snapshot.get('content') or ''),
                request_id=input_snapshot.get('request_id'),
                model_name=(run.config_snapshot or {}).get('model_name'),
                entrypoint=str(input_snapshot.get('entrypoint') or 'chat'),
                module=input_snapshot.get('module'),
            )

            async def trace_hook(node_key: str, status: str, output: dict[str, Any]) -> None:
                progress_map = {
                    'loading_context': 0.2,
                    'planning': 0.35,
                    'retrieval': 0.5,
                    'model_response': 0.8,
                    'memory_update': 0.95,
                }
                progress = progress_map.get(node_key, run.progress)
                async with async_db_session() as trace_db:
                    trace_run = await agent_run_dao.get_owned(trace_db, run_id=run_id, user_id=user_id)
                    if trace_run is None:
                        return
                    trace_run.stage = node_key
                    trace_run.progress = progress
                    if status != 'running':
                        await agent_run_dao.add_step(
                            trace_db,
                            data={
                                'run_id': run_id,
                                'step_no': await agent_run_dao.next_step_no(trace_db, run_id=run_id),
                                'node_key': node_key,
                                'status': status,
                                'input_snapshot': {},
                                'output_snapshot': output,
                                'started_time': timezone.now(),
                                'finished_time': timezone.now(),
                            },
                        )
                    await trace_db.commit()
                await agent_event_bus.publish(
                    run_id,
                    {
                        'run_id': run_id,
                        'status': run.status,
                        'stage': run.stage,
                        'progress': progress,
                        'step': {'node_key': node_key, 'status': status, 'output': output},
                    },
                )

            try:
                await agent_event_bus.publish(
                    run_id,
                    {'run_id': run_id, 'status': run.status, 'stage': run.stage, 'progress': run.progress},
                )
                session = await self.send_message(
                    db=db,
                    session_id=session_id,
                    user_id=user_id,
                    params=params,
                    trace_hook=trace_hook,
                )
                run.status = 'succeeded'
                run.stage = 'completed'
                run.progress = 1.0
                run.result_summary = session.last_summary or '申论教练回复已完成。'
                run.result_payload = {
                    'session_id': session.id,
                    'message_count': len(session.messages),
                    'last_summary': session.last_summary,
                }
                run.finished_time = timezone.now()
                await agent_run_dao.add_step(
                    db,
                    data={
                        'run_id': run_id,
                        'step_no': await agent_run_dao.next_step_no(db, run_id=run_id),
                        'node_key': 'completed',
                        'status': 'succeeded',
                        'input_snapshot': {},
                        'output_snapshot': run.result_payload,
                        'started_time': run.finished_time,
                        'finished_time': run.finished_time,
                    },
                )
                await db.commit()
                await agent_event_bus.publish(
                    run_id,
                    {
                        'run_id': run_id,
                        'status': run.status,
                        'stage': run.stage,
                        'progress': run.progress,
                        'result': run.result_payload,
                    },
                )
            except Exception as exc:
                await db.rollback()
                run = await agent_run_dao.get_owned(db, run_id=run_id, user_id=user_id)
                if run is None:
                    return
                run.status = 'failed'
                run.stage = 'failed'
                run.progress = 1.0
                run.error_code = type(exc).__name__
                run.error_message = str(exc)[:2000]
                run.finished_time = timezone.now()
                await agent_run_dao.add_step(
                    db,
                    data={
                        'run_id': run_id,
                        'step_no': await agent_run_dao.next_step_no(db, run_id=run_id),
                        'node_key': 'failed',
                        'status': 'failed',
                        'input_snapshot': {},
                        'output_snapshot': None,
                        'error_message': str(exc)[:2000],
                        'started_time': run.started_time,
                        'finished_time': run.finished_time,
                    },
                )
                await db.commit()
                await agent_event_bus.publish(
                    run_id,
                    {
                        'run_id': run_id,
                        'status': run.status,
                        'stage': run.stage,
                        'progress': run.progress,
                        'error_message': run.error_message,
                    },
                )

    @staticmethod
    def _start_run_result(run_id: int, status: str) -> StartCoachRunResult:
        return StartCoachRunResult(
            run_id=run_id,
            agent_key='shenlun.coach',
            status=status,
            stream_url=f'/api/v1/agent/shenlun/coach/runs/{run_id}/stream',
        )

    async def create_session(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        title: str,
        grading_run_id: int | None,
    ) -> CoachSessionRead:
        context: dict[str, Any] = {}
        if grading_run_id:
            run = await self._get_owned_run(db=db, run_id=grading_run_id, user_id=user_id)
            context['grading_run_id'] = run.id
            context['grading_subject_id'] = run.subject_id
            await self._learn_from_grading(db=db, user_id=user_id, run=run)
        session = await shenlun_coach_session_dao.create_session(
            db,
            data={'user_id': user_id, 'title': title, 'context_snapshot': context},
        )
        await db.commit()
        return await self.get_session(db=db, session_id=session.id, user_id=user_id)

    async def get_session(self, *, db: AsyncSession, session_id: int, user_id: int) -> CoachSessionRead:
        session = await shenlun_coach_session_dao.get_owned_for_update(
            db,
            session_id=session_id,
            user_id=user_id,
        )
        if session is None:
            raise errors.NotFoundError(msg='教练会话不存在')
        messages = await shenlun_coach_message_dao.list_recent(db, session_id=session.id, limit=100)
        return CoachSessionRead(
            id=session.id,
            title=session.title,
            status=session.status,
            context_snapshot=session.context_snapshot or {},
            last_summary=session.last_summary,
            messages=[self._message_read(item) for item in messages],
            created_time=session.created_time,
            updated_time=session.updated_time,
        )

    async def list_sessions(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        status: str | None = None,
    ) -> list[CoachSessionListRead]:
        sessions = await shenlun_coach_session_dao.list_user(db, user_id=user_id, status=status)
        return [
            CoachSessionListRead(
                id=session.id,
                title=session.title,
                status=session.status,
                last_summary=session.last_summary,
                created_time=session.created_time,
                updated_time=session.updated_time,
            )
            for session in sessions
        ]

    async def archive_session(self, *, db: AsyncSession, session_id: int, user_id: int) -> CoachSessionRead:
        session = await shenlun_coach_session_dao.get_owned_for_update(
            db,
            session_id=session_id,
            user_id=user_id,
        )
        if session is None:
            raise errors.NotFoundError(msg='教练会话不存在')
        session.status = 'archived'
        await db.commit()
        return await self.get_session(db=db, session_id=session_id, user_id=user_id)

    async def list_memories(self, *, db: AsyncSession, user_id: int) -> list[CoachMemoryRead]:
        """获取用户的长期训练记忆。"""
        memories = await shenlun_coach_memory_dao.list_user(db, user_id=user_id, limit=100)
        return [
            CoachMemoryRead(
                id=item.id,
                memory_key=item.memory_key,
                memory_type=item.memory_type,
                content=item.content,
                confidence=item.confidence,
                source_ref=item.source_ref,
                evidence=item.evidence or {},
                last_seen_time=item.last_seen_time,
            )
            for item in memories
        ]

    async def send_message(
        self,
        *,
        db: AsyncSession,
        session_id: int,
        user_id: int,
        params: CoachMessageParam,
        trace_hook: Callable[[str, str, dict[str, Any]], Awaitable[None]] | None = None,
    ) -> CoachSessionRead:
        session = await shenlun_coach_session_dao.get_owned_for_update(
            db,
            session_id=session_id,
            user_id=user_id,
        )
        if session is None:
            raise errors.NotFoundError(msg='教练会话不存在')
        if session.status != 'active':
            raise errors.ConflictError(msg='教练会话已归档')
        request_ref = f'shenlun_coach:{user_id}:{session_id}:{params.request_id or uuid4().hex}'
        existing = await self._get_message_by_request(db=db, session_id=session_id, request_id=params.request_id)
        if existing is not None:
            return await self.get_session(db=db, session_id=session_id, user_id=user_id)

        decision = await agent_quota_service.consume_shenlun_coach(
            db=db,
            user_id=user_id,
            request_ref=request_ref,
        )
        try:
            await shenlun_coach_message_dao.create_message(
                db,
                data={
                    'session_id': session_id,
                    'user_id': user_id,
                    'role': 'user',
                    'content': params.content.strip(),
                    'request_id': params.request_id,
                    'metadata_payload': {'request_id': params.request_id} if params.request_id else {},
                },
            )
            await self._trace(trace_hook, 'loading_context', 'running')
            context = await self._build_context(db=db, user_id=user_id, session=session)
            await self._trace(
                trace_hook,
                'loading_context',
                'succeeded',
                {'evidence_card_count': len(context.get('evidence_cards') or [])},
            )
            await self._trace(trace_hook, 'planning', 'running')
            intent_plan = build_intent_plan(
                text=params.content.strip(),
                entrypoint=params.entrypoint,
                module_hint=params.module or str((session.context_snapshot or {}).get('module') or ''),
                has_attempt=bool(context.get('recent_grading_cases')),
                subject_ids=[
                    int(item['run_id'])
                    for item in context.get('recent_grading_cases') or []
                    if item.get('run_id')
                ],
            )
            await self._trace(trace_hook, 'planning', 'succeeded', intent_plan)
            await self._trace(trace_hook, 'retrieval', 'running')
            recommendations = []
            if intent_plan['action'] == 'recommend':
                recommendations = await coach_recommendation_service.recommend(
                    db=db,
                    user_id=user_id,
                    module=str(intent_plan['module']),
                    limit=5,
                )
            context['intent_plan'] = intent_plan
            context['candidate_questions'] = recommendations
            await self._trace(
                trace_hook,
                'retrieval',
                'succeeded',
                {
                    'recommended_question_count': len(recommendations),
                    'evidence_card_count': len(context.get('evidence_cards') or []),
                },
            )
            await self._trace(trace_hook, 'model_response', 'running')
            response = await self._invoke_coach(
                db=db,
                context=context,
                user_content=params.content.strip(),
                model_name=params.model_name,
            )
            await self._trace(
                trace_hook,
                'model_response',
                'succeeded',
                {
                    'model_name': response.get('model_name'),
                    'context_ref_count': len(response.get('context_refs') or []),
                },
            )
            coach_message = await shenlun_coach_message_dao.create_message(
                db,
                data={
                    'session_id': session_id,
                    'user_id': user_id,
                    'role': 'coach',
                    'content': response['content'],
                    'request_id': None,
                    'metadata_payload': {
                        'request_id': params.request_id,
                        'model_name': response.get('model_name'),
                        'context_refs': response.get('context_refs') or [],
                        'intent_plan': intent_plan,
                        'recommended_questions': recommendations,
                    },
                },
            )
            session.last_summary = response.get('summary') or response['content'][:300]
            session.context_snapshot = {
                **(session.context_snapshot or {}),
                'last_request_id': params.request_id,
                'last_message_id': coach_message.id,
                'last_context_refs': response.get('context_refs') or [],
                'entrypoint': intent_plan['entrypoint'],
                'action': intent_plan['action'],
                'module': intent_plan['module'],
            }
            await self._trace(trace_hook, 'memory_update', 'running')
            await self._update_memories_from_response(
                db=db,
                user_id=user_id,
                response=response,
                source_ref=f'coach_session:{session_id}:message:{coach_message.id}',
            )
            await self._trace(
                trace_hook,
                'memory_update',
                'succeeded',
                {'memory_update_count': len(response.get('memory_updates') or [])},
            )
            await db.commit()
        except Exception:
            await db.rollback()
            await agent_quota_service.refund_shenlun_coach(
                db=db,
                user_id=user_id,
                request_ref=request_ref,
                decision=decision,
            )
            await db.commit()
            raise
        return await self.get_session(db=db, session_id=session_id, user_id=user_id)

    async def generate_plan(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        params: GenerateTrainingPlanParam,
    ) -> TrainingPlanRead:
        request_ref = f'shenlun_coach:plan:{user_id}:{params.request_id or uuid4().hex}'
        if params.request_id:
            existing_plan = await self._get_plan_by_request(db=db, user_id=user_id, request_id=params.request_id)
            if existing_plan is not None:
                return await self.get_plan(db=db, plan_id=existing_plan.id, user_id=user_id)
        decision = await agent_quota_service.consume_shenlun_coach(
            db=db,
            user_id=user_id,
            request_ref=request_ref,
        )
        try:
            context = await self._build_user_context(db=db, user_id=user_id)
            response = await self._invoke_coach(
                db=db,
                context=context,
                user_content=(
                    f'请生成一个{params.days}天申论训练计划。训练目标：{params.goal}；'
                    f'每天可投入{params.daily_minutes}分钟。只输出 JSON，包含 items 数组，'
                    '每项有 day、task_type、title、instruction、target。'
                ),
                model_name=params.model_name,
                plan_mode=True,
            )
            plan = await shenlun_training_plan_dao.create_plan(
                db,
                data={
                    'user_id': user_id,
                    'request_id': params.request_id,
                    'title': f'申论训练计划（{params.days}天）',
                    'status': 'active',
                    'goal': params.goal,
                    'start_date': timezone.now(),
                    'end_date': timezone.now() + timedelta(days=params.days),
                    'summary': {
                        'daily_minutes': params.daily_minutes,
                        'model_name': response.get('model_name'),
                        'request_id': params.request_id,
                    },
                },
            )
            rows = []
            for index, item in enumerate((response.get('items') or [])[: params.days], start=1):
                if not isinstance(item, dict):
                    continue
                day = int(item.get('day') or index)
                task_type = str(item.get('task_type') or 'practice')
                if task_type not in {'practice', 'review', 'reflection'}:
                    task_type = 'practice'
                rows.append({
                    'plan_id': plan.id,
                    'user_id': user_id,
                    'due_date': timezone.now() + timedelta(days=max(0, day - 1)),
                    'task_type': task_type,
                    'title': str(item.get('title') or f'第{day}天训练')[:200],
                    'instruction': str(item.get('instruction') or '')[:20000],
                    'target': item.get('target') if isinstance(item.get('target'), dict) else {},
                })
            if not rows:
                rows = self._fallback_plan_rows(plan_id=plan.id, user_id=user_id, days=params.days)
            await shenlun_training_plan_item_dao.batch_create(db, rows=rows)
            await db.commit()
        except Exception:
            await db.rollback()
            await agent_quota_service.refund_shenlun_coach(
                db=db,
                user_id=user_id,
                request_ref=request_ref,
                decision=decision,
            )
            await db.commit()
            raise
        return await self.get_plan(db=db, plan_id=plan.id, user_id=user_id)

    async def get_plan(self, *, db: AsyncSession, plan_id: int, user_id: int) -> TrainingPlanRead:
        plan = await shenlun_training_plan_dao.get_owned(db, plan_id=plan_id, user_id=user_id)
        if plan is None:
            raise errors.NotFoundError(msg='训练计划不存在')
        items = await shenlun_training_plan_item_dao.list_plan(db, plan_id=plan.id)
        return TrainingPlanRead(
            id=plan.id,
            title=plan.title,
            status=plan.status,
            goal=plan.goal,
            start_date=plan.start_date,
            end_date=plan.end_date,
            summary=plan.summary or {},
            items=[self._plan_item_read(item) for item in items],
            created_time=plan.created_time,
        )

    async def list_plans(self, *, db: AsyncSession, user_id: int) -> list[TrainingPlanListRead]:
        plans = await shenlun_training_plan_dao.list_user(db, user_id=user_id, limit=100)
        return [
            TrainingPlanListRead(
                id=plan.id,
                title=plan.title,
                status=plan.status,
                goal=plan.goal,
                start_date=plan.start_date,
                end_date=plan.end_date,
                summary=plan.summary or {},
                created_time=plan.created_time,
            )
            for plan in plans
        ]

    async def complete_plan_item(self, *, db: AsyncSession, item_id: int, user_id: int) -> TrainingPlanRead:
        item = await shenlun_training_plan_item_dao.get_owned(db, item_id=item_id, user_id=user_id)
        if item is None:
            raise errors.NotFoundError(msg='训练计划项不存在')
        await shenlun_training_plan_item_dao.complete(db, item=item, completed_time=timezone.now())
        plan = await shenlun_training_plan_dao.get_owned(db, plan_id=item.plan_id, user_id=user_id)
        if plan is not None:
            plan_items = await shenlun_training_plan_item_dao.list_plan(db, plan_id=plan.id)
            if plan_items and all(plan_item.status == 'completed' for plan_item in plan_items):
                plan.status = 'completed'
        await db.commit()
        return await self.get_plan(db=db, plan_id=item.plan_id, user_id=user_id)

    async def analytics(self, *, db: AsyncSession, user_id: int) -> CoachAnalyticsRead:
        runs = list(
            (
                await db.execute(
                    select(AgentRun)
                    .where(
                        AgentRun.user_id == user_id,
                        AgentRun.agent_key == 'shenlun.grading',
                        AgentRun.status == 'succeeded',
                        AgentRun.deleted == 0,
                    )
                    .order_by(AgentRun.created_time.asc(), AgentRun.id.asc())
                    .limit(200)
                )
            )
            .scalars()
            .all()
        )
        rates: list[float] = []
        score_trend: list[dict[str, Any]] = []
        strengths: list[str] = []
        weaknesses: list[str] = []
        for run in runs:
            payload = run.result_payload or {}
            max_score = float(payload.get('display_max_score') or payload.get('max_score') or 0)
            score = float(payload.get('display_score') or 0)
            if max_score > 0:
                rate = score / max_score
                rates.append(rate)
                score_trend.append({'run_id': run.id, 'score_rate': round(rate, 4)})
            summary = payload.get('summary') or {}
            strengths.extend(str(item) for item in summary.get('strengths') or [])
            weaknesses.extend(str(item) for item in summary.get('weaknesses') or [])
        plans = await shenlun_training_plan_dao.list_user(db, user_id=user_id, limit=100)
        pending, completed = 0, 0
        for plan in plans:
            items = await shenlun_training_plan_item_dao.list_plan(db, plan_id=plan.id)
            pending += sum(item.status in {'pending', 'in_progress'} for item in items)
            completed += sum(item.status == 'completed' for item in items)
        return CoachAnalyticsRead(
            grading_count=len(runs),
            average_score_rate=round(sum(rates) / len(rates), 4) if rates else None,
            latest_score_rate=round(rates[-1], 4) if rates else None,
            score_trend=score_trend,
            strengths=self._top_terms(strengths),
            weaknesses=self._top_terms(weaknesses),
            active_plan_count=sum(plan.status == 'active' for plan in plans),
            pending_task_count=pending,
            completed_task_count=completed,
        )

    async def _build_context(self, *, db: AsyncSession, user_id: int, session: ShenlunCoachSession) -> dict[str, Any]:
        return {
            **await self._build_user_context(db=db, user_id=user_id),
            'session_context': session.context_snapshot or {},
            'recent_messages': [
                {'role': item.role, 'content': item.content}
                for item in await shenlun_coach_message_dao.list_recent(db, session_id=session.id, limit=20)
            ],
        }

    async def _build_user_context(self, *, db: AsyncSession, user_id: int) -> dict[str, Any]:
        memories = await shenlun_coach_memory_dao.list_user(db, user_id=user_id, limit=30)
        runs = list(
            (
                await db.execute(
                    select(AgentRun)
                    .where(
                        AgentRun.user_id == user_id,
                        AgentRun.agent_key == 'shenlun.grading',
                        AgentRun.status == 'succeeded',
                        AgentRun.deleted == 0,
                    )
                    .order_by(AgentRun.created_time.desc(), AgentRun.id.desc())
                    .limit(8)
                )
            )
            .scalars()
            .all()
        )
        grading_cases = []
        question_ids: list[int] = []
        evidence_cards: list[dict[str, Any]] = []
        for run in runs:
            payload = run.result_payload or {}
            question_id = (payload.get('rubric') or {}).get('question_id')
            if question_id:
                question_ids.append(int(question_id))
            grading_cases.append({
                'run_id': run.id,
                'question_id': question_id,
                'score': payload.get('display_score'),
                'max_score': payload.get('display_max_score'),
                'summary': payload.get('summary'),
                'suggestions': payload.get('optimization_suggestions') or [],
                'point_matches': payload.get('point_matches') or [],
            })
            evidence_cards.extend(self._grading_evidence_cards(run=run, payload=payload))
        questions = []
        if question_ids:
            questions = list(
                (
                    await db.execute(
                        select(QbQuestion).where(
                            QbQuestion.id.in_(set(question_ids)),
                            QbQuestion.deleted == 0,
                        )
                    )
                )
                .scalars()
                .all()
            )
        evidence_cards.extend(
            {
                'evidence_id': f'question:{question.id}',
                'source_type': 'question',
                'source_ref': str(question.id),
                'claim': question.code,
                'content': str(question.stem or '')[:1600],
            }
            for question in questions
        )
        notes = []
        if question_ids:
            notes = list(
                (
                    await db.execute(
                        select(QbQuestionNote).where(
                            QbQuestionNote.user_id == user_id,
                            QbQuestionNote.question_id.in_(set(question_ids)),
                            QbQuestionNote.deleted == 0,
                        )
                    )
                )
                .scalars()
                .all()
            )
        evidence_cards.extend(
            {
                'evidence_id': f'note:{note.id}',
                'source_type': 'personal_note',
                'source_ref': str(note.id),
                'claim': '用户笔记',
                'content': str(note.content or '')[:1200],
            }
            for note in notes
        )
        memory_payload = [
            {
                'key': item.memory_key,
                'type': item.memory_type,
                'content': item.content,
                'confidence': item.confidence,
            }
            for item in memories
        ]
        evidence_cards.extend(
            {
                'evidence_id': f"memory:{item['key']}",
                'source_type': 'weakness_profile' if item['type'] == 'weakness' else 'memory',
                'source_ref': item['key'],
                'claim': item['type'],
                'content': item['content'],
            }
            for item in memory_payload
        )
        return {
            'memories': memory_payload,
            'recent_grading_cases': grading_cases,
            'evidence_cards': evidence_cards[:80],
            'evidence_sufficiency': {
                'card_count': len(evidence_cards),
                'grading_report_count': sum(card['source_type'] == 'grading_report' for card in evidence_cards),
                'personal_note_count': sum(card['source_type'] == 'personal_note' for card in evidence_cards),
                'has_current_grading_context': bool(grading_cases),
            },
        }

    @staticmethod
    def _grading_evidence_cards(*, run: AgentRun, payload: dict[str, Any]) -> list[dict[str, Any]]:
        cards: list[dict[str, Any]] = []
        summary = payload.get('summary') or {}
        if summary:
            cards.append({
                'evidence_id': f'grading_run:{run.id}:summary',
                'source_type': 'grading_report',
                'source_ref': f'grading_run:{run.id}',
                'claim': '批改结论',
                'content': json.dumps(summary, ensure_ascii=False, default=str)[:1500],
            })
        cards.extend(
            {
                'evidence_id': f'grading_run:{run.id}:point:{index}',
                'source_type': 'grading_report',
                'source_ref': f'grading_run:{run.id}',
                'claim': str(match.get('point') or match.get('point_key') or '采分点'),
                'content': json.dumps(match, ensure_ascii=False, default=str)[:1200],
            }
            for index, match in enumerate(payload.get('point_matches') or [])
            if isinstance(match, dict)
        )
        return cards

    @staticmethod
    async def _trace(
        hook: Callable[[str, str, dict[str, Any]], Awaitable[None]] | None,
        node_key: str,
        status: str,
        output: dict[str, Any] | None = None,
    ) -> None:
        if hook is not None:
            await hook(node_key, status, output or {})

    async def _invoke_coach(
        self,
        *,
        db: AsyncSession,
        context: dict[str, Any],
        user_content: str,
        model_name: str | None,
        plan_mode: bool = False,
    ) -> dict[str, Any]:
        model, provider = await resolve_agent_model(db=db, model_name=model_name)
        system = (
            '你是专业、温和、严格基于证据的申论训练教练。'
            '必须区分题库事实、批改报告和推测，不得编造。'
            '必须遵守 intent_plan 中的 action、scope 和 sources；推荐题只能来自 candidate_questions。'
            '涉及用户事实时必须引用 evidence_id；证据不足时明确说明，不得补写事实。'
            '回复应包含可执行的下一步，默认使用简洁中文。'
        )
        schema = (
            '{"content":"教练回复","summary":"摘要","memory_updates":[{"key":"weakness.xxx",'
            '"type":"weakness","content":"...","confidence":0.8}],"context_refs":["grading_run:1"],'
            '"recommended_question_ids":[1,2]}'
        )
        if plan_mode:
            schema = '{"items":[{"day":1,"task_type":"practice","title":"...","instruction":"...","target":{}}]}'
        prompt = (
            f'用户训练上下文：{json.dumps(context, ensure_ascii=False, default=str)}\n'
            f'用户请求：{user_content}\n只返回 JSON，格式：{schema}'
        )
        from backend.plugin.ai.schema.chat import AIChat, AIChatMessage
        from backend.plugin.ai.service.chat_service import ai_chat_service

        raw = await ai_chat_service.raw_chat(
            db=db,
            chat=AIChat(
                provider_id=provider.id,
                model_id=model.model_id,
                messages=[AIChatMessage(role='system', content=system), AIChatMessage(role='user', content=prompt)],
                temperature=0.2,
                max_tokens=7000 if plan_mode else 3000,
                seed=7,
                extra_body={'response_format': {'type': 'json_object'}},
            ),
        )
        content = raw.get('content') if isinstance(raw, dict) else raw
        payload = self._parse_json(str(content or ''))
        payload['model_name'] = model.model_id
        return payload

    async def _learn_from_grading(self, *, db: AsyncSession, user_id: int, run: AgentRun) -> None:
        payload = run.result_payload or {}
        summary = payload.get('summary') or {}
        for memory_type in ('weakness', 'strength'):
            values = summary.get(f'{memory_type}es') if memory_type == 'weakness' else summary.get('strengths')
            for value in values or []:
                text = str(value).strip()
                if not text:
                    continue
                digest = hashlib.sha256(text.encode()).hexdigest()[:16]
                await shenlun_coach_memory_dao.upsert(
                    db,
                    user_id=user_id,
                    memory_key=f'{memory_type}.grading.{digest}',
                    data={
                        'memory_type': memory_type,
                        'content': text,
                        'confidence': 0.75,
                        'source_ref': f'grading_run:{run.id}',
                        'evidence': {'run_id': run.id},
                        'last_seen_time': timezone.now(),
                    },
                )

    async def _update_memories_from_response(
        self,
        *,
        db: AsyncSession,
        user_id: int,
        response: dict[str, Any],
        source_ref: str,
    ) -> None:
        for item in response.get('memory_updates') or []:
            if not isinstance(item, dict) or not item.get('key') or not item.get('content'):
                continue
            memory_type = str(item.get('type') or 'preference')
            if memory_type not in {'weakness', 'strength', 'preference', 'goal'}:
                memory_type = 'preference'
            await shenlun_coach_memory_dao.upsert(
                db,
                user_id=user_id,
                memory_key=str(item['key'])[:120],
                data={
                    'memory_type': memory_type,
                    'content': str(item['content']),
                    'confidence': max(0.0, min(1.0, float(item.get('confidence') or 0.5))),
                    'source_ref': source_ref,
                    'evidence': {'source_ref': source_ref},
                    'last_seen_time': timezone.now(),
                },
            )

    async def _get_owned_run(self, *, db: AsyncSession, run_id: int, user_id: int) -> AgentRun:
        run = await self._get_run(db=db, run_id=run_id, user_id=user_id)
        if run is None or run.status != 'succeeded':
            raise errors.NotFoundError(msg='可用的批改结果不存在')
        return run

    @staticmethod
    async def _get_run(*, db: AsyncSession, run_id: int, user_id: int) -> AgentRun | None:
        stmt = select(AgentRun).where(AgentRun.id == run_id, AgentRun.user_id == user_id, AgentRun.deleted == 0)
        return (await db.execute(stmt)).scalars().first()

    @staticmethod
    async def _get_plan_by_request(
        *,
        db: AsyncSession,
        user_id: int,
        request_id: str,
    ) -> Any | None:
        stmt = select(ShenlunTrainingPlan).where(
            ShenlunTrainingPlan.user_id == user_id,
            ShenlunTrainingPlan.request_id == request_id,
            ShenlunTrainingPlan.deleted == 0,
        )
        return (await db.execute(stmt)).scalars().first()

    @staticmethod
    async def _get_message_by_request(
        *,
        db: AsyncSession,
        session_id: int,
        request_id: str | None,
    ) -> ShenlunCoachMessage | None:
        if not request_id:
            return None
        stmt = select(ShenlunCoachMessage).where(
            ShenlunCoachMessage.session_id == session_id,
            ShenlunCoachMessage.request_id == request_id,
            ShenlunCoachMessage.deleted == 0,
        )
        return (await db.execute(stmt)).scalars().first()

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        content = content.strip().removeprefix('```json').removesuffix('```').strip()
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            start, end = content.find('{'), content.rfind('}')
            if start < 0 or end <= start:
                raise errors.ServerError(msg='教练返回格式异常') from None
            payload = json.loads(content[start : end + 1])
        if not isinstance(payload, dict):
            raise errors.ServerError(msg='教练返回结构异常')
        return payload

    @staticmethod
    def _fallback_plan_rows(*, plan_id: int, user_id: int, days: int) -> list[dict[str, Any]]:
        rows = []
        for day in range(1, days + 1):
            task_type = 'review' if day % 3 == 0 else 'practice'
            rows.append({
                'plan_id': plan_id,
                'user_id': user_id,
                'due_date': timezone.now() + timedelta(days=day - 1),
                'task_type': task_type,
                'title': f'第{day}天申论{ "复盘" if task_type == "review" else "专项练习" }',
                'instruction': '完成一道申论题，记录命中采分点、缺失点和下一次改进动作。',
                'target': {'min_minutes': 30},
            })
        return rows

    @staticmethod
    def _top_terms(values: list[str]) -> list[str]:
        counts: dict[str, int] = {}
        for value in values:
            counts[value] = counts.get(value, 0) + 1
        return [key for key, _ in sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:8]]

    @staticmethod
    def _message_read(item: ShenlunCoachMessage) -> Any:
        from backend.plugin.agent.schema.coach import CoachMessageRead
        return CoachMessageRead(
            id=item.id,
            role=item.role,
            content=item.content,
            metadata_payload=item.metadata_payload or {},
            created_time=item.created_time,
        )

    @staticmethod
    def _plan_item_read(item: ShenlunTrainingPlanItem) -> Any:
        from backend.plugin.agent.schema.coach import TrainingPlanItemRead
        return TrainingPlanItemRead(
            id=item.id,
            due_date=item.due_date,
            task_type=item.task_type,
            title=item.title,
            instruction=item.instruction,
            target=item.target or {},
            status=item.status,
            completed_time=item.completed_time,
        )


shenlun_coach_service = ShenlunCoachService()
