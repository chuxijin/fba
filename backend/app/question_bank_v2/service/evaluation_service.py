import json
import re

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from html import unescape
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.question_bank_v2.crud.crud_evaluation import (
    EvaluationAttemptContext,
    evaluation_run_dao,
)
from backend.app.question_bank_v2.crud.crud_material import question_material_dao
from backend.app.question_bank_v2.crud.crud_practice import (
    practice_response_dao,
    practice_session_dao,
    question_attempt_dao,
)
from backend.app.question_bank_v2.crud.crud_question import question_explanation_dao
from backend.app.question_bank_v2.model.evaluation import QbEvaluationRun
from backend.app.question_bank_v2.service.review_schedule_service import review_schedule_service
from backend.app.question_bank_v2.service.statistics_service import statistics_service
from backend.common.exception import errors
from backend.plugin.agent.schema.grading import GradingRunRead, StartShenlunGradingParam, StartShenlunGradingResult
from backend.plugin.agent.service.shenlun_service import shenlun_grading_service
from backend.plugin.ai.model.model import AIModel
from backend.plugin.ai.model.provider import AIProvider
from backend.plugin.ai.schema.chat import AIChat, AIChatMessage
from backend.plugin.ai.service.chat_service import ai_chat_service
from backend.utils.timezone import timezone

DEFAULT_MODEL_NAME = 'gpt-5.4'
ATTEMPT_PROMPT_VERSION = 'qbank_v2_subjective_grading_v1'
SESSION_SUMMARY_PROMPT_VERSION = 'qbank_v2_session_summary_v1'
AI_CONFIDENCE_THRESHOLD = Decimal('0.6000')
CORRECT_SCORE_RATE = Decimal('0.6000')
AI_BATCH_SIZE = 5
SUBJECTIVE_METHODS = {'manual', 'rubric', 'custom'}


@dataclass(frozen=True, slots=True)
class PreparedAttemptEvaluation:
    """已创建审计运行、等待模型返回的主观题评测项"""

    context: EvaluationAttemptContext
    run: QbEvaluationRun
    prompt_item: dict[str, Any]


class EvaluationService:
    """题库 V2 可审计 AI 判分与学习总结服务类"""

    @staticmethod
    def _strip_markup(content: str | None) -> str:
        """把常见 HTML 内容转换为适合模型读取的纯文本"""
        if not content:
            return ''
        text = re.sub(r'<br\s*/?>', '\n', content, flags=re.IGNORECASE)
        text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)
        return re.sub(r'\s+', ' ', unescape(text)).strip()

    @staticmethod
    def _stringify_response(value: Any) -> str:
        """稳定序列化客户端结构化答案"""
        if isinstance(value, str):
            return value.strip()
        if value is None:
            return ''
        if isinstance(value, (dict, list)):
            return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
        return str(value).strip()

    @staticmethod
    def _normalise_decimal(value: Any, *, digits: str) -> Decimal | None:
        """把外部模型数值约束到数据库精度"""
        if value is None or (isinstance(value, str) and not value):
            return None
        try:
            return Decimal(str(value)).quantize(Decimal(digits), rounding=ROUND_HALF_UP)
        except (InvalidOperation, TypeError, ValueError):
            return None

    @staticmethod
    def _requires_manual_review(*, confidence: Decimal | None, requested: bool) -> bool:
        """缺失或低置信度结果必须进入人工复核"""
        return requested or confidence is None or confidence < AI_CONFIDENCE_THRESHOLD

    @staticmethod
    def _is_correct(*, score: Decimal, max_score: Decimal) -> bool:
        """把主观题得分映射为掌握度所需的二值结果"""
        return max_score > 0 and score >= max_score * CORRECT_SCORE_RATE

    @staticmethod
    def _extract_text_content(message: dict[str, Any]) -> str:
        """兼容文本和多内容块两类聊天响应"""
        content = message.get('content')
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            return '\n'.join(
                str(item.get('text')).strip()
                for item in content
                if isinstance(item, dict) and item.get('text')
            )
        return ''

    @staticmethod
    def _extract_json_payload(content: str) -> dict[str, Any]:
        """从模型文本中提取单个 JSON 对象"""
        text = content.strip()
        fenced = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, flags=re.DOTALL | re.IGNORECASE)
        if fenced:
            text = fenced.group(1)
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            start = text.find('{')
            end = text.rfind('}')
            if start < 0 or end <= start:
                raise ValueError('模型未返回有效 JSON') from None
            try:
                payload = json.loads(text[start : end + 1])
            except json.JSONDecodeError as exc:
                raise ValueError('模型返回 JSON 无法解析') from exc
        if not isinstance(payload, dict):
            raise TypeError('模型返回结果不是 JSON 对象')
        return payload

    @staticmethod
    async def _resolve_runtime_model(
        *,
        db: AsyncSession,
        model_name: str | None,
    ) -> tuple[AIModel, AIProvider]:
        """获取指定或默认的已启用模型与服务商"""
        resolved_name = model_name or DEFAULT_MODEL_NAME
        stmt = (
            select(AIModel, AIProvider)
            .join(AIProvider, AIProvider.id == AIModel.provider_id)
            .where(
                AIModel.model_id == resolved_name,
                AIModel.status == 1,
                AIProvider.status == 1,
            )
            .order_by(AIModel.id.desc())
            .limit(1)
        )
        row = (await db.execute(stmt)).first()
        if row is None:
            raise errors.NotFoundError(msg=f'未找到可用的 AI 模型：{resolved_name}')
        return row[0], row[1]

    @classmethod
    async def _invoke_json_chat(
        cls,
        *,
        db: AsyncSession,
        model: AIModel,
        provider: AIProvider,
        messages: list[AIChatMessage],
        max_tokens: int,
    ) -> dict[str, Any]:
        """调用统一 AI 插件并解析 JSON 结果"""
        response = await ai_chat_service.raw_chat(
            db=db,
            chat=AIChat(
                provider_id=provider.id,
                model_id=model.model_id,
                messages=messages,
                temperature=0.2,
                max_tokens=max_tokens,
                seed=7,
            ),
        )
        return cls._extract_json_payload(cls._extract_text_content(response))

    @staticmethod
    def _attempt_messages(items: list[dict[str, Any]]) -> list[AIChatMessage]:
        """构建批量主观题评分提示词"""
        system_prompt = (
            '你是严谨的中文考试阅卷助手。只能依据题目、材料、考生答案、参考答案、评分量规和解析评分，'
            '不得补造依据。若依据不足或答案无法理解，必须标记 failed。只返回 JSON。'
        )
        user_prompt = (
            '批量评分并返回 {"evaluations":[...]}。每项字段必须包含 attempt_id、status、score、confidence、'
            'grading_summary、strengths、missing_points、improvement_suggestions、encouragement、'
            'needs_manual_review、failure_reason。score 必须在 0 与 max_score 之间，confidence 必须在 0 到 1。'
            f'\n题目数据：{json.dumps(items, ensure_ascii=False, default=str)}'
        )
        return [
            AIChatMessage(role='system', content=system_prompt),
            AIChatMessage(role='user', content=user_prompt),
        ]

    @staticmethod
    def _summary_messages(payload: dict[str, Any]) -> list[AIChatMessage]:
        """构建会话学习总结提示词"""
        system_prompt = (
            '你是中文学习教练。基于给定练习事实生成简洁、可信、可执行的总结，不得推测未提供的信息。'
            '只返回 JSON。'
        )
        user_prompt = (
            '返回字段 overview、strengths、high_frequency_issues、weak_knowledge_points、next_actions、'
            'encouragement、needs_manual_review。'
            f'\n会话数据：{json.dumps(payload, ensure_ascii=False, default=str)}'
        )
        return [
            AIChatMessage(role='system', content=system_prompt),
            AIChatMessage(role='user', content=user_prompt),
        ]

    @classmethod
    async def _build_attempt_payload(
        cls,
        *,
        db: AsyncSession,
        context: EvaluationAttemptContext,
        explanations: Sequence[Any] | None = None,
        material_rows: Sequence[dict[str, Any]] | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """构建内部审计快照和发送给模型的最小输入"""
        if explanations is None:
            explanations = await question_explanation_dao.get_all(db, context.question.id)
        explanation = next(
            (item.content for item in explanations if item.status == 'published' and item.is_default),
            next((item.content for item in explanations if item.status == 'published'), ''),
        )
        if material_rows is None:
            material_rows = await question_material_dao.get_all_by_questions(db, [context.question.id])
        materials = [
            {
                'title': item['title'],
                'content': cls._strip_markup(item['content']),
                'role': item['role'],
            }
            for item in material_rows
        ]
        answer_data = dict(context.answer.answer_data or {})
        grading_config = dict(context.answer.grading_config or {})
        reference_context = {
            'answer_data': answer_data,
            'grading_config': grading_config,
            'explanation': cls._strip_markup(explanation),
        }
        request_payload = {
            'attempt_id': context.attempt.id,
            'question_id': context.attempt.question_id,
            'question_type': context.question.question_type,
            'stem': cls._strip_markup(context.question.stem),
            'materials': materials,
            'user_response': cls._stringify_response(context.attempt.response_data),
            'max_score': str(context.session_item.max_score),
            'reference_context': reference_context,
        }
        prompt_item = dict(request_payload)
        has_reference = bool(answer_data or grading_config or reference_context['explanation'])
        prompt_item['has_reference'] = has_reference
        return request_payload, prompt_item

    @staticmethod
    def _ensure_attempt_supported(context: EvaluationAttemptContext) -> None:
        """校验作答允许进入 AI 主观题判分"""
        if context.answer.grading_method not in SUBJECTIVE_METHODS:
            raise errors.RequestError(msg='当前作答不是需要外部评测的主观题')
        if not EvaluationService._stringify_response(context.attempt.response_data):
            raise errors.RequestError(msg='请先提交有效答案后再进行 AI 判分')
        if context.session.mode in {'exam', 'mock'} and context.session.status not in {'submitted', 'graded'}:
            raise errors.ForbiddenError(msg='考试或模考必须交卷后才能进行 AI 判分')

    @staticmethod
    async def _update_current_response(
        *,
        db: AsyncSession,
        context: EvaluationAttemptContext,
        status: str,
        is_correct: bool | None,
        score: Decimal | None,
    ) -> None:
        """仅在该作答仍为最近提交时更新会话当前状态"""
        if not await question_attempt_dao.is_latest_for_item(db, context.attempt):
            return
        response = await practice_response_dao.get(
            db,
            session_id=context.session.id,
            session_item_id=context.session_item.id,
            for_update=True,
        )
        if response is None:
            return
        response.grading_status = status
        response.is_correct = is_correct
        response.score = score
        response.status = 'graded' if status == 'graded' else 'review_required'
        response.graded_time = timezone.now() if status == 'graded' else None
        await db.flush()

    @classmethod
    async def _mark_attempt_failed(
        cls,
        *,
        db: AsyncSession,
        item: PreparedAttemptEvaluation,
        code: str,
        message: str,
    ) -> QbEvaluationRun:
        """完成失败运行，并把尚未判分的当前作答标记为失败"""
        now = timezone.now()
        item.run.status = 'failed'
        item.run.error_code = code[:64]
        item.run.error_message = message[:2000]
        item.run.needs_manual_review = True
        item.run.finished_time = now
        if item.context.attempt.is_correct is None:
            item.context.attempt.grading_status = 'failed'
            item.context.attempt.grading_method = 'ai'
            item.context.attempt.grading_result = {
                **dict(item.context.attempt.grading_result or {}),
                'evaluation_run_id': item.run.id,
                'error_code': code,
            }
            await cls._update_current_response(
                db=db,
                context=item.context,
                status='failed',
                is_correct=None,
                score=None,
            )
        await db.flush()
        return item.run

    @classmethod
    async def _complete_attempt(
        cls,
        *,
        db: AsyncSession,
        item: PreparedAttemptEvaluation,
        raw_result: dict[str, Any],
    ) -> QbEvaluationRun:
        """校验模型结果并完成运行与可重建投影"""
        if str(raw_result.get('status') or 'succeeded').lower() != 'succeeded':
            return await cls._mark_attempt_failed(
                db=db,
                item=item,
                code='MODEL_REJECTED',
                message=str(raw_result.get('failure_reason') or '模型未完成该题评分'),
            )
        score = cls._normalise_decimal(raw_result.get('score'), digits='0.01')
        if score is None:
            return await cls._mark_attempt_failed(
                db=db,
                item=item,
                code='INVALID_SCORE',
                message='模型未返回有效分数',
            )
        max_score = item.context.session_item.max_score
        score = min(max(score, Decimal(0)), max_score)
        confidence = cls._normalise_decimal(raw_result.get('confidence'), digits='0.0001')
        if confidence is not None:
            confidence = min(max(confidence, Decimal(0)), Decimal(1))
        needs_manual_review = cls._requires_manual_review(
            confidence=confidence,
            requested=bool(raw_result.get('needs_manual_review')),
        )
        result_payload = {
            'grading_summary': str(raw_result.get('grading_summary') or '').strip() or None,
            'strengths': raw_result.get('strengths') if isinstance(raw_result.get('strengths'), list) else [],
            'missing_points': (
                raw_result.get('missing_points') if isinstance(raw_result.get('missing_points'), list) else []
            ),
            'improvement_suggestions': (
                raw_result.get('improvement_suggestions')
                if isinstance(raw_result.get('improvement_suggestions'), list)
                else []
            ),
            'encouragement': str(raw_result.get('encouragement') or '').strip() or None,
            'projection_applied': False,
        }
        item.run.status = 'succeeded'
        item.run.score = score
        item.run.max_score = max_score
        item.run.confidence = confidence
        item.run.needs_manual_review = needs_manual_review
        item.run.summary_text = result_payload['grading_summary']
        item.run.result_payload = result_payload
        item.run.finished_time = timezone.now()

        if item.context.attempt.is_correct is None:
            if needs_manual_review:
                item.context.attempt.grading_status = 'review_required'
                item.context.attempt.grading_method = 'ai'
                item.context.attempt.grading_result = {
                    **dict(item.context.attempt.grading_result or {}),
                    'evaluation_run_id': item.run.id,
                    'confidence': str(confidence) if confidence is not None else None,
                }
                await cls._update_current_response(
                    db=db,
                    context=item.context,
                    status='review_required',
                    is_correct=None,
                    score=None,
                )
            else:
                item.context.attempt.is_correct = cls._is_correct(score=score, max_score=max_score)
                item.context.attempt.score = score
                item.context.attempt.grading_status = 'graded'
                item.context.attempt.grading_method = 'ai'
                item.context.attempt.grading_result = {
                    **dict(item.context.attempt.grading_result or {}),
                    'evaluation_run_id': item.run.id,
                    'confidence': str(confidence),
                }
                result_payload['projection_applied'] = True
                item.run.result_payload = result_payload
                await review_schedule_service.apply_delayed_grade(
                    db=db,
                    attempt=item.context.attempt,
                    session_item=item.context.session_item,
                )
                await statistics_service.apply_delayed_grade(
                    db=db,
                    attempt=item.context.attempt,
                    max_score=max_score,
                )
                await cls._update_current_response(
                    db=db,
                    context=item.context,
                    status='graded',
                    is_correct=item.context.attempt.is_correct,
                    score=score,
                )
        await db.flush()
        return item.run

    @classmethod
    async def _prepare_attempts(
        cls,
        *,
        db: AsyncSession,
        contexts: Sequence[EvaluationAttemptContext],
        force_regenerate: bool,
    ) -> tuple[list[QbEvaluationRun], list[PreparedAttemptEvaluation]]:
        """创建替代链并分离可复用结果与待执行项"""
        completed: list[QbEvaluationRun] = []
        prepared: list[PreparedAttemptEvaluation] = []
        trigger_source = 'retry' if force_regenerate else 'manual'
        attempt_ids = [context.attempt.id for context in contexts]
        question_ids = list({context.question.id for context in contexts})
        latest_runs = await evaluation_run_dao.get_latest_attempts(
            db,
            attempt_ids=attempt_ids,
            for_update=True,
        )
        explanation_rows = await question_explanation_dao.get_all_by_questions(db, question_ids)
        material_rows = await question_material_dao.get_all_by_questions(db, question_ids)
        explanations_by_question: dict[int, list[Any]] = {}
        materials_by_question: dict[int, list[dict[str, Any]]] = {}
        for explanation in explanation_rows:
            explanations_by_question.setdefault(explanation.question_id, []).append(explanation)
        for material in material_rows:
            materials_by_question.setdefault(material['question_id'], []).append(material)
        for context in contexts:
            cls._ensure_attempt_supported(context)
            latest = latest_runs.get(context.attempt.id)
            if latest is not None and not force_regenerate:
                completed.append(latest)
                continue
            if latest is not None:
                latest.is_latest = False
            request_payload, prompt_item = await cls._build_attempt_payload(
                db=db,
                context=context,
                explanations=explanations_by_question.get(context.question.id, []),
                material_rows=materials_by_question.get(context.question.id, []),
            )
            run = await evaluation_run_dao.create(
                db,
                {
                    'user_id': context.attempt.user_id,
                    'purpose': 'attempt_grading',
                    'engine_type': 'ai',
                    'attempt_id': context.attempt.id,
                    'supersedes_id': latest.id if latest is not None else None,
                    'trigger_source': trigger_source,
                    'status': 'running',
                    'prompt_version': ATTEMPT_PROMPT_VERSION,
                    'rubric_version': f'question:{context.question.id}',
                    'max_score': context.session_item.max_score,
                    'request_payload': request_payload,
                    'started_time': timezone.now(),
                    'is_latest': True,
                },
            )
            work = PreparedAttemptEvaluation(context=context, run=run, prompt_item=prompt_item)
            if not prompt_item['has_reference']:
                completed.append(
                    await cls._mark_attempt_failed(
                        db=db,
                        item=work,
                        code='REFERENCE_MISSING',
                        message='题目缺少参考答案、评分量规或解析，无法稳定进行 AI 判分',
                    )
                )
                continue
            prepared.append(work)
        return completed, prepared

    @classmethod
    async def _run_prepared_attempts(
        cls,
        *,
        db: AsyncSession,
        items: list[PreparedAttemptEvaluation],
        model_name: str | None,
    ) -> list[QbEvaluationRun]:
        """按固定小批次执行模型调用，降低整场主观题评测请求数"""
        if not items:
            return []
        try:
            model, provider = await cls._resolve_runtime_model(db=db, model_name=model_name)
        except Exception as exc:
            return [
                await cls._mark_attempt_failed(
                    db=db,
                    item=item,
                    code='MODEL_UNAVAILABLE',
                    message=str(exc) or 'AI 模型不可用',
                )
                for item in items
            ]

        completed: list[QbEvaluationRun] = []
        for start in range(0, len(items), AI_BATCH_SIZE):
            chunk = items[start : start + AI_BATCH_SIZE]
            for item in chunk:
                item.run.provider = provider.name
                item.run.model_name = model.model_id
            try:
                payload = await cls._invoke_json_chat(
                    db=db,
                    model=model,
                    provider=provider,
                    messages=cls._attempt_messages([item.prompt_item for item in chunk]),
                    max_tokens=3000,
                )
                raw_evaluations = payload.get('evaluations')
                if not isinstance(raw_evaluations, list):
                    raise TypeError('模型返回缺少 evaluations 列表')
                response_map = {
                    int(raw['attempt_id']): raw
                    for raw in raw_evaluations
                    if isinstance(raw, dict) and str(raw.get('attempt_id', '')).isdigit()
                }
            except Exception as exc:
                completed.extend(
                    [
                        await cls._mark_attempt_failed(
                            db=db,
                            item=item,
                            code='MODEL_CALL_FAILED',
                            message=str(exc) or 'AI 判分调用失败',
                        )
                        for item in chunk
                    ]
                )
                continue
            for item in chunk:
                raw_result = response_map.get(item.context.attempt.id)
                if raw_result is None:
                    completed.append(
                        await cls._mark_attempt_failed(
                            db=db,
                            item=item,
                            code='RESULT_MISSING',
                            message='模型未返回该题的评测结果',
                        )
                    )
                else:
                    completed.append(await cls._complete_attempt(db=db, item=item, raw_result=raw_result))
        return completed

    @classmethod
    async def evaluate_attempt(
        cls,
        *,
        db: AsyncSession,
        attempt_id: int,
        user_id: int,
        force_regenerate: bool,
        model_name: str | None,
    ) -> QbEvaluationRun:
        """评测当前用户的一次主观题作答"""
        context = await evaluation_run_dao.get_attempt_context(
            db,
            attempt_id=attempt_id,
            user_id=user_id,
            for_update=True,
        )
        if context is None:
            raise errors.NotFoundError(msg='作答记录不存在')
        completed, prepared = await cls._prepare_attempts(
            db=db,
            contexts=[context],
            force_regenerate=force_regenerate,
        )
        completed.extend(await cls._run_prepared_attempts(db=db, items=prepared, model_name=model_name))
        if not completed:
            raise errors.ServerError(msg='AI 判分未生成运行结果')
        await practice_session_dao.refresh_aggregates(db, context.session)
        return completed[0]

    @staticmethod
    async def get_latest_attempt(
        *,
        db: AsyncSession,
        attempt_id: int,
        user_id: int,
    ) -> QbEvaluationRun:
        """获取当前用户一次作答的最新 AI 判分"""
        context = await evaluation_run_dao.get_attempt_context(
            db,
            attempt_id=attempt_id,
            user_id=user_id,
        )
        if context is None:
            raise errors.NotFoundError(msg='作答记录不存在')
        run = await evaluation_run_dao.get_latest_attempt(db, attempt_id=attempt_id)
        if run is None:
            raise errors.NotFoundError(msg='该作答暂无 AI 判分结果')
        return run

    @classmethod
    async def evaluate_session_attempts(
        cls,
        *,
        db: AsyncSession,
        session_key: str,
        user_id: int,
        force_regenerate: bool,
        model_name: str | None,
    ) -> list[QbEvaluationRun]:
        """批量评测会话中每道主观题的最近一次提交"""
        session = await practice_session_dao.get_by_key(db, session_key, user_id=user_id, for_update=True)
        if session is None:
            raise errors.NotFoundError(msg='练习会话不存在')
        if session.mode in {'exam', 'mock'} and session.status not in {'submitted', 'graded'}:
            raise errors.ForbiddenError(msg='考试或模考必须交卷后才能进行 AI 判分')
        contexts = await evaluation_run_dao.list_latest_subjective_contexts(
            db,
            session_id=session.id,
            user_id=user_id,
        )
        if not contexts:
            raise errors.RequestError(msg='当前会话没有已提交的主观题作答')
        completed, prepared = await cls._prepare_attempts(
            db=db,
            contexts=contexts,
            force_regenerate=force_regenerate,
        )
        completed.extend(await cls._run_prepared_attempts(db=db, items=prepared, model_name=model_name))
        await practice_session_dao.refresh_aggregates(db, session)
        return sorted(completed, key=lambda run: (run.attempt_id or 0, run.id))

    @classmethod
    async def generate_session_summary(
        cls,
        *,
        db: AsyncSession,
        session_key: str,
        user_id: int,
        force_regenerate: bool,
        model_name: str | None,
    ) -> QbEvaluationRun:
        """基于答题卡事实和当前 AI 判分生成可替代的会话总结"""
        session = await practice_session_dao.get_by_key(db, session_key, user_id=user_id, for_update=True)
        if session is None:
            raise errors.NotFoundError(msg='练习会话不存在')
        if session.status not in {'submitted', 'graded'}:
            raise errors.ForbiddenError(msg='请先提交练习会话，再生成 AI 总结')
        latest = await evaluation_run_dao.get_latest_session(db, session_id=session.id, for_update=True)
        if latest is not None and not force_regenerate:
            return latest
        if latest is not None:
            latest.is_latest = False
        rows = await practice_session_dao.get_report_items(db, session.id)
        attempt_runs = await evaluation_run_dao.list_latest_attempt_runs_by_session(db, session_id=session.id)
        run_summaries = {
            run.attempt_id: {
                'score': str(run.score) if run.score is not None else None,
                'max_score': str(run.max_score) if run.max_score is not None else None,
                'summary': run.summary_text,
                'needs_manual_review': run.needs_manual_review,
            }
            for run in attempt_runs
        }
        request_payload = {
            'session_id': session.id,
            'mode': session.mode,
            'source_type': session.source_type,
            'total_items': session.total_items,
            'answered_items': session.answered_items,
            'correct_items': session.correct_items,
            'score': str(session.score),
            'items': [
                {
                    'position': row['position'],
                    'question_id': row['question_id'],
                    'is_correct': row['is_correct'],
                    'score': str(row['score']) if row['score'] is not None else None,
                    'max_score': str(row['max_score']),
                    'grading_status': row['grading_status'],
                }
                for row in rows[:100]
            ],
            'subjective_evaluations': run_summaries,
        }
        run = await evaluation_run_dao.create(
            db,
            {
                'user_id': user_id,
                'purpose': 'session_summary',
                'engine_type': 'ai',
                'session_id': session.id,
                'supersedes_id': latest.id if latest is not None else None,
                'trigger_source': 'retry' if force_regenerate else 'manual',
                'status': 'running',
                'prompt_version': SESSION_SUMMARY_PROMPT_VERSION,
                'score': session.score,
                'max_score': sum((row['max_score'] for row in rows), start=Decimal(0)),
                'request_payload': request_payload,
                'started_time': timezone.now(),
                'is_latest': True,
            },
        )
        try:
            model, provider = await cls._resolve_runtime_model(db=db, model_name=model_name)
            run.provider = provider.name
            run.model_name = model.model_id
            payload = await cls._invoke_json_chat(
                db=db,
                model=model,
                provider=provider,
                messages=cls._summary_messages(request_payload),
                max_tokens=2200,
            )
            result_payload = {
                'overview': payload.get('overview'),
                'strengths': payload.get('strengths') if isinstance(payload.get('strengths'), list) else [],
                'high_frequency_issues': (
                    payload.get('high_frequency_issues')
                    if isinstance(payload.get('high_frequency_issues'), list)
                    else []
                ),
                'weak_knowledge_points': (
                    payload.get('weak_knowledge_points')
                    if isinstance(payload.get('weak_knowledge_points'), list)
                    else []
                ),
                'next_actions': payload.get('next_actions') if isinstance(payload.get('next_actions'), list) else [],
                'encouragement': payload.get('encouragement'),
            }
            run.status = 'succeeded'
            run.summary_text = str(payload.get('overview') or '').strip() or None
            run.result_payload = result_payload
            run.needs_manual_review = bool(payload.get('needs_manual_review'))
        except Exception as exc:
            run.status = 'failed'
            run.error_code = 'SUMMARY_FAILED'
            run.error_message = (str(exc) or 'AI 总结生成失败')[:2000]
        run.finished_time = timezone.now()
        await db.flush()
        return run

    @staticmethod
    async def get_latest_session_summary(
        *,
        db: AsyncSession,
        session_key: str,
        user_id: int,
    ) -> QbEvaluationRun:
        """获取当前用户会话的最新 AI 总结"""
        session = await practice_session_dao.get_by_key(db, session_key, user_id=user_id)
        if session is None:
            raise errors.NotFoundError(msg='练习会话不存在')
        run = await evaluation_run_dao.get_latest_session(db, session_id=session.id)
        if run is None:
            raise errors.NotFoundError(msg='当前会话暂无 AI 总结')
        return run

    @classmethod
    async def start_shenlun_agent(
        cls,
        *,
        db: AsyncSession,
        attempt_id: int,
        user_id: int,
    ) -> StartShenlunGradingResult:
        """使用新申论 Agent 对一次主观题作答启动深度批改"""
        context = await evaluation_run_dao.get_attempt_context(
            db,
            attempt_id=attempt_id,
            user_id=user_id,
        )
        if context is None:
            raise errors.NotFoundError(msg='作答记录不存在')
        cls._ensure_attempt_supported(context)
        return await shenlun_grading_service.start(
            db=db,
            attempt_id=attempt_id,
            user_id=user_id,
            params=StartShenlunGradingParam(),
        )

    @staticmethod
    async def get_shenlun_agent(
        *,
        db: AsyncSession,
        task_id: int,
        user_id: int,
    ) -> GradingRunRead:
        """获取当前用户的申论 Agent 批改详情"""
        return await shenlun_grading_service.get_detail(db=db, run_id=task_id, user_id=user_id)


evaluation_service: EvaluationService = EvaluationService()
