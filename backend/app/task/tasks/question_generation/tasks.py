#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import logging

from pathlib import Path
from typing import Any

from backend.app.question_generation.crud import candidate_dao, material_dao, task_dao
from backend.app.task.celery import celery_app
from backend.database.db import async_db_session
from backend.plugin.agents.schema import QuestionGenerationState
from backend.plugin.agents.service.common.llm import LLMClient
from backend.plugin.agents.service.common.orchestrator import NodeContext
from backend.plugin.agents.service.common.orchestrator.usage import build_usage_summary
from backend.plugin.agents.service.common.prompts import PromptLoader
from backend.plugin.agents.service.common.streaming import event_bus
from backend.plugin.agents.service.question_generation import build_pipeline
from backend.utils.timezone import timezone

logger = logging.getLogger(__name__)

_AGENT_DIR = Path(__file__).resolve().parents[4] / 'plugin' / 'agents' / 'service' / 'question_generation'


def _status_for_stage(stage: str) -> str:
    """
    根据 pipeline 阶段映射任务状态

    :param stage: 阶段标识
    :return:
    """
    if stage in {'load_profile', 'analyze_article', 'mine_passages', 'review_passages'}:
        return 'analyzing'
    if stage in {'plan_question_types', 'review_question_types', 'plan_blueprints'}:
        return 'planning'
    if stage in {'draft_questions', 'design_options'}:
        return 'generating'
    if stage == 'review_generation':
        return 'reviewing'
    return 'generating'


def _build_snapshot(state: QuestionGenerationState) -> dict[str, Any]:
    """
    构建出题状态快照

    :param state: 出题状态
    :return:
    """
    return {
        'profile': state.profile,
        'article_analysis': state.article_analysis,
        'passage_plan': state.passage_plan,
        'selected_passages': state.selected_passages,
        'passage_reviews': state.passage_reviews,
        'discarded_passages': state.discarded_passages,
        'question_type_opportunities': state.question_type_opportunities,
        'type_reviews': state.type_reviews,
        'discarded_type_opportunities': state.discarded_type_opportunities,
        'blueprints': state.blueprints,
        'candidate_count': len(state.candidates),
        'question_reviews': state.question_reviews,
        'discarded_candidates': state.discarded_candidates,
        'qc': state.qc,
        'traces': [item.model_dump(mode='json') for item in state.traces],
        'usage_summary': build_usage_summary(state.traces),
    }


@celery_app.task(name='question_generation:run_task')
async def run_question_generation_task(task_id: int) -> dict[str, Any]:
    """
    执行 AI 出题任务

    :param task_id: 任务 ID
    :return:
    """
    try:
        return await _run_question_generation_task(task_id)
    except Exception as exc:
        logger.exception('AI 出题任务失败 task_id=%s: %s', task_id, exc)
        await _mark_task_failed(task_id=task_id, exc=exc)
        return {'success': False, 'task_id': task_id, 'error': str(exc)}


async def _run_question_generation_task(task_id: int) -> dict[str, Any]:
    """
    执行 AI 出题任务实现

    :param task_id: 任务 ID
    :return:
    """
    async with async_db_session() as db:
        task = await task_dao.get(db, task_id)
        if task is None:
            raise RuntimeError(f'出题任务不存在: {task_id}')

        material = await material_dao.get(db, task.material_id)
        if material is None:
            raise RuntimeError(f'出题素材不存在: {task.material_id}')

        await task_dao.update_progress(
            db,
            task,
            status='analyzing',
            stage='load_profile',
            progress=0.01,
        )
        await db.commit()

        state = QuestionGenerationState(
            task_id=task.id,
            user_id=task.user_id,
            provider_id=task.provider_id,
            primary_model=task.model_id,
            material_id=material.id,
            material_title=material.title,
            material_content=material.content,
            exam=task.exam,
            subject=task.subject,
            section=task.section,
            target_question_types=task.target_question_types,
            question_count=task.question_count,
        )
        ctx = NodeContext(
            state=state,
            db=db,
            event_bus=event_bus,
            llm=LLMClient(
                provider_id=task.provider_id,
                primary_model_id=task.model_id,
                mini_model_id=task.mini_model_id,
            ),
            prompts=PromptLoader(base_dir=_AGENT_DIR / 'prompts'),
        )

        async def _checkpoint(stage: str, progress: float, snapshot: dict[str, Any]) -> None:
            task_ref = await task_dao.get(db, task_id)
            if task_ref is None:
                return
            merged_snapshot = _build_snapshot(state)
            merged_snapshot.update(snapshot)
            task_ref.target_question_types = state.target_question_types
            task_ref.question_count = state.question_count
            await task_dao.update_progress(
                db,
                task_ref,
                status=_status_for_stage(stage),
                stage=stage,
                progress=progress,
                state_snapshot=merged_snapshot,
            )
            await db.commit()

        pipeline = build_pipeline(on_checkpoint=_checkpoint)
        await pipeline.run(ctx)

        material_status = 'usable'
        if state.passage_plan and not state.passage_plan.get('can_generate'):
            material_status = 'manual_review'
        if state.passage_plan:
            await material_dao.set_process_result(
                db,
                material,
                status=material_status,
                process_result=state.passage_plan,
            )

        candidates = await candidate_dao.batch_create_from_agent(
            db,
            task_id=task.id,
            material_id=material.id,
            rows=state.candidates,
            created_by=task.created_by,
            qc_result=state.qc,
        )
        result_summary = {
            'candidate_count': len(candidates),
            'qc': state.qc,
            'usage_summary': build_usage_summary(state.traces),
            'finished_at': timezone.to_str(timezone.now()),
        }
        task_ref = await task_dao.get(db, task_id)
        if task_ref is None:
            raise RuntimeError(f'出题任务不存在: {task_id}')
        await task_dao.mark_completed(db, task_ref, result_summary=result_summary)
        await db.commit()

        return {
            'success': True,
            'task_id': task_id,
            'candidate_count': len(candidates),
        }


async def _mark_task_failed(*, task_id: int, exc: Exception) -> None:
    """
    标记任务失败

    :param task_id: 任务 ID
    :param exc: 异常
    :return:
    """
    async with async_db_session() as db:
        task = await task_dao.get(db, task_id)
        if task is None:
            return
        await task_dao.mark_failed(
            db,
            task,
            error_code=type(exc).__name__,
            error_message=str(exc),
        )
        await db.commit()
