#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import asyncio

from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.common.exception import errors
from backend.common.log import log
from backend.core.conf import settings
from backend.database.db import async_db_session
from backend.plugin.agents.crud import agent_task_dao
from backend.plugin.agents.model import AgentTask
from backend.plugin.agents.schema import (
    AgentReport,
    AgentType,
    GradingDetail,
    GradingOcrResult,
    GradingStartParam,
    GradingStartResult,
    GradingState,
    TaskStatus,
)
from backend.plugin.agents.service.common.llm import LLMClient
from backend.plugin.agents.service.common.ocr import OCRClient
from backend.plugin.agents.service.common.orchestrator import NodeContext
from backend.plugin.agents.service.common.prompts import PromptLoader
from backend.plugin.agents.service.common.quota import quota_provider
from backend.plugin.agents.service.common.streaming import event_bus
from backend.plugin.agents.service.shenlun import build_pipeline as build_shenlun_pipeline

_AGENT_DIRS: dict[AgentType, Path] = {
    AgentType.shenlun: Path(__file__).resolve().parent / 'shenlun',
}

_PIPELINE_BUILDERS = {
    AgentType.shenlun: build_shenlun_pipeline,
}


def _friendly_grading_error_message(error_message: str | None) -> str:
    """
    转换为用户可理解的批改失败提示

    :param error_message: 原始错误信息
    :return:
    """
    message = str(error_message or '').strip()
    if not message:
        return '批改暂时失败，请稍后重试'

    lower_message = message.lower()
    internal_patterns = (
        'llm',
        'max_tokens',
        'token limit',
        'modelresponse',
        'output_type',
        'output_retries',
        'answeranalyzeroutput',
        'validationerror',
        'pydantic',
        'traceback',
        'json',
    )
    if any(pattern in lower_message for pattern in internal_patterns):
        return '本次批改生成内容较长，AI 暂时没能稳定完成评分。请稍后重新批改，或适当精简答案后再试。'

    if len(message) > 80:
        return '批改暂时失败，请稍后重试'

    return message


class GradingService:
    """批改业务服务"""

    async def start(self, db: AsyncSession, *, params: GradingStartParam) -> GradingStartResult:
        """
        启动批改任务: 权益预检 + 建任务 + 后台跑 pipeline

        :param db: 数据库会话
        :param params: 启动参数
        :return:
        """
        await quota_provider.ensure_quota(db, user_id=params.user_id, agent_type=params.agent_type)

        task = await agent_task_dao.create_task(
            db=db,
            agent_type=str(getattr(params.agent_type, 'value', params.agent_type)),
            user_id=params.user_id,
            provider_id=params.provider_id,
            model_id=params.model_id,
            input_payload=params.model_dump(mode='json'),
        )
        await db.commit()

        asyncio.create_task(self._run_in_background(task_id=task.id))

        stream_url = f'{settings.FASTAPI_API_V1_PATH}/agents/grading/{task.id}/stream'
        return GradingStartResult(
            task_id=task.id,
            agent_type=params.agent_type,
            status=TaskStatus.pending,
            stream_url=stream_url,
        )

    def run_background(self, task_id: int) -> None:
        """
        启动后台批改任务

        :param task_id: 任务 ID
        :return:
        """
        asyncio.create_task(self._run_in_background(task_id=task_id))

    async def get_detail(self, db: AsyncSession, task_id: int) -> GradingDetail:
        """
        获取任务详情

        :param db: 数据库会话
        :param task_id: 任务 ID
        :return:
        """
        task = await agent_task_dao.get(db=db, pk=task_id)
        if task is None:
            raise errors.NotFoundError(msg='批改任务不存在')
        return self._to_detail(task)

    async def recognize_user_answer(
        self,
        files: list[Any],
        provider: str | None = None,
    ) -> GradingOcrResult:
        """
        识别考生答卷图片为归一化文本, 不入库不启动批改

        :param files: UploadFile 列表
        :param provider: OCR provider 名称, 留空走 settings.OCR_PROVIDER 默认
        :return:
        """
        if not files:
            raise errors.RequestError(msg='请至少上传 1 张图片')

        images: list[tuple[bytes, str, str]] = []
        for f in files:
            content = await f.read()
            if not content:
                continue
            filename = str(getattr(f, 'filename', None) or 'image.jpg')
            content_type = str(getattr(f, 'content_type', None) or 'image/jpeg')
            images.append((content, filename, content_type))

        if not images:
            raise errors.RequestError(msg='所有上传图片均为空, 请重新选择')

        client = OCRClient(provider_name=provider)
        text = await client.recognize_images(images, scene='subjective_answer')
        return GradingOcrResult(
            text=text,
            image_count=len(images),
            provider=str(provider or ''),
        )

    async def _run_in_background(self, task_id: int) -> None:
        """
        后台跑 pipeline, 独立 session 避免与 API 请求 session 冲突

        :param task_id: 任务 ID
        :return:
        """
        try:
            await self._execute(task_id)
        except Exception as e:
            log.exception(f'Agent 批改任务失败 task_id={task_id}: {e!s}')
            await self._mark_failed(
                task_id,
                error_code=type(e).__name__,
                error_message=_friendly_grading_error_message(str(e)),
            )

    async def _execute(self, task_id: int) -> None:
        """
        在独立 session 下执行 pipeline 并落库

        :param task_id: 任务 ID
        :return:
        """
        async with async_db_session() as db:
            task = await agent_task_dao.get(db=db, pk=task_id)
            if task is None:
                raise errors.NotFoundError(msg=f'批改任务不存在 task_id={task_id}')

            await agent_task_dao.mark_running(db=db, task=task, stage='intake', progress=0.05)
            await db.commit()

            agent_type = AgentType(task.agent_type)
            state = self._build_state(task)
            ctx = NodeContext(
                state=state,
                db=db,
                event_bus=event_bus,
                llm=LLMClient(
                    provider_id=task.provider_id,
                    primary_model_id=task.model_id,
                    mini_model_id=task.input_payload.get('mini_model_id'),
                ),
                prompts=PromptLoader(base_dir=_AGENT_DIRS[agent_type] / 'prompts'),
            )

            pipeline_builder = _PIPELINE_BUILDERS.get(agent_type)
            if pipeline_builder is None:
                raise errors.RequestError(msg=f'尚未支持的 agent 类型: {agent_type.value}')

            async def _checkpoint(stage: str, progress: float, snapshot: dict[str, Any]) -> None:
                task_ref = await agent_task_dao.get(db=db, pk=task_id)
                if task_ref is not None:
                    await agent_task_dao.update_progress(
                        db=db,
                        task=task_ref,
                        stage=stage,
                        progress=progress,
                        state_snapshot=snapshot,
                    )
                    await db.commit()

            pipeline = pipeline_builder(on_checkpoint=_checkpoint)
            await pipeline.run(ctx)

            report = self._state_to_report(ctx.state, agent_type)
            if ctx.state.qc is not None and not ctx.state.qc.passed:
                task = await agent_task_dao.get(db=db, pk=task_id)
                if task is None:
                    raise errors.NotFoundError(msg=f'批改任务不存在 task_id={task_id}')
                await agent_task_dao.mark_failed(
                    db=db,
                    task=task,
                    error_code='QualityCheckFailed',
                    error_message='; '.join(ctx.state.qc.notes) or '质检未通过',
                    report=report.model_dump(mode='json'),
                    traces=[trace.model_dump(mode='json') for trace in ctx.state.traces],
                    quota_consumed=False,
                )
                await db.commit()
                return

            task = await self._get_task_for_update(db=db, task_id=task_id)
            if task is None:
                return

            quota_decision = await quota_provider.consume_quota(
                db=db,
                user_id=task.user_id,
                agent_type=agent_type,
            )
            await agent_task_dao.mark_completed(
                db=db,
                task=task,
                report=report.model_dump(mode='json'),
                traces=[trace.model_dump(mode='json') for trace in ctx.state.traces],
                quota_consumed=quota_decision.allowed,
            )
            await db.commit()

    async def _mark_failed(self, task_id: int, *, error_code: str, error_message: str) -> None:
        """
        失败时用新 session 标记失败, 避免污染原 session

        :param task_id: 任务 ID
        :param error_code: 错误码
        :param error_message: 错误信息
        :return:
        """
        async with async_db_session() as db:
            task = await agent_task_dao.get(db=db, pk=task_id)
            if task is None:
                return
            await agent_task_dao.mark_failed(
                db=db,
                task=task,
                error_code=error_code,
                error_message=error_message,
            )
            await db.commit()

    @staticmethod
    async def _get_task_for_update(db: AsyncSession, task_id: int) -> AgentTask | None:
        """
        锁定并获取任务

        :param db: 数据库会话
        :param task_id: 任务 ID
        :return:
        """
        stmt = select(AgentTask).where(AgentTask.id == task_id).with_for_update()
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    def _build_state(task: AgentTask) -> GradingState:
        """
        从持久化 task 还原运行时 state

        :param task: 任务对象
        :return:
        """
        payload: dict[str, Any] = task.input_payload or {}
        return GradingState(
            task_id=task.id,
            user_id=task.user_id,
            provider_id=task.provider_id,
            primary_model=task.model_id,
            question_stem=payload.get('question_stem', ''),
            question=payload.get('question', ''),
            materials=payload.get('materials', ''),
            reference_answers=payload.get('reference_answers', []),
            user_answer_text=payload.get('user_answer_text', ''),
            score_total=payload.get('score_total'),
        )

    @staticmethod
    def _state_to_report(state: GradingState, agent_type: AgentType) -> AgentReport:
        """
        把运行时 state 投影成最终报告

        :param state: 运行时状态
        :param agent_type: agent 类型
        :return:
        """
        return AgentReport(
            agent_type=agent_type,
            score_card=state.score_card,
            key_points=state.key_points,
            issues=state.issues,
            suggestions=state.suggestions,
            rewritten_text=state.rewritten_text,
            qc=state.qc,
            traces=state.traces,
        )

    @staticmethod
    def _to_detail(task: AgentTask) -> GradingDetail:
        """
        模型对象转为详情 schema

        :param task: 任务对象
        :return:
        """
        report = None
        if task.report:
            report = AgentReport.model_validate(task.report)
        return GradingDetail(
            id=task.id,
            agent_type=AgentType(task.agent_type),
            user_id=task.user_id,
            status=TaskStatus(task.status),
            stage=task.stage,
            progress=task.progress,
            report=report,
            state_snapshot=task.state_snapshot,
            error_code=task.error_code,
            error_message=_friendly_grading_error_message(task.error_message) if task.error_message else None,
            created_time=task.created_time,
            updated_time=task.updated_time,
        )


grading_service: GradingService = GradingService()
