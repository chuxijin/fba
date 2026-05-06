#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import re

from collections.abc import Iterable, Sequence
from decimal import ROUND_HALF_UP, Decimal
from html import unescape
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.question_bank.crud.crud_ai_evaluation import practice_ai_evaluation_dao
from backend.app.question_bank.crud.crud_practice_record import practice_record_dao
from backend.app.question_bank.crud.crud_practice_session import practice_session_dao
from backend.app.question_bank.model import PracticeAIEvaluation, PracticeRecord, PracticeSession, Question
from backend.app.question_bank.model.question import QuestionAnalysis
from backend.common.exception import errors
from backend.plugin.ai.model.model import AIModel
from backend.plugin.ai.model.provider import AIProvider
from backend.plugin.ai.schema.chat import AIChat, AIChatMessage
from backend.plugin.ai.service.chat_service import ai_chat_service
from backend.utils.timezone import timezone

SUBJECTIVE_QUESTION_TYPES = {'shortAnswer'}
AI_DEFAULT_MODEL_NAME = 'gpt-5.4'
QUESTION_EVAL_PROMPT_VERSION = 'subjective_eval_v1'
SESSION_SUMMARY_PROMPT_VERSION = 'session_summary_v1'
QUESTION_EVAL_THRESHOLD = Decimal('0.60')
QUESTION_EVAL_CHUNK_SIZE = 5
PLACEHOLDER_TEXTS = {'暂无题干', '暂无解析', '0'}


class PracticeAIEvaluationService:
    """练习 AI 评估服务类"""

    @staticmethod
    def _strip_html(content: str | None) -> str:
        """
        去除 HTML 标签

        :param content: 原始内容
        :return:
        """
        if not content:
            return ''

        text = re.sub(r'<br\s*/?>', '\n', content, flags=re.IGNORECASE)
        text = re.sub(r'</p>', '\n', text, flags=re.IGNORECASE)
        text = re.sub(r'<[^>]+>', '', text)
        text = unescape(text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    @classmethod
    def _is_placeholder_text(cls, content: str | None) -> bool:
        """
        判断是否为占位文本

        :param content: 文本内容
        :return:
        """
        text = cls._strip_html(content)
        if not text:
            return True
        return text in PLACEHOLDER_TEXTS

    @staticmethod
    def _stringify_answer(user_answer: Any) -> str:
        """
        将答案转换为文本

        :param user_answer: 用户答案
        :return:
        """
        if isinstance(user_answer, str):
            return user_answer.strip()
        if isinstance(user_answer, list):
            parts = [str(item).strip() for item in user_answer if str(item).strip()]
            return '；'.join(parts)
        if isinstance(user_answer, dict):
            return json.dumps(user_answer, ensure_ascii=False, sort_keys=True)
        if user_answer is None:
            return ''
        return str(user_answer).strip()

    @staticmethod
    def _normalize_decimal(value: Any, *, digits: str = '0.01') -> Decimal | None:
        """
        规范化 Decimal

        :param value: 原始值
        :param digits: 精度
        :return:
        """
        if value is None or value == '':
            return None

        try:
            decimal_value = Decimal(str(value))
        except Exception:
            return None

        return decimal_value.quantize(Decimal(digits), rounding=ROUND_HALF_UP)

    @staticmethod
    def _normalize_confidence(value: Any) -> Decimal | None:
        """
        规范化置信度

        :param value: 原始值
        :return:
        """
        confidence = PracticeAIEvaluationService._normalize_decimal(value, digits='0.0001')
        if confidence is None:
            return None
        if confidence < Decimal('0'):
            return Decimal('0')
        if confidence > Decimal('1'):
            return Decimal('1')
        return confidence

    @staticmethod
    def _chunk_items(items: Sequence[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
        """
        对列表进行分块

        :param items: 原始列表
        :param size: 分块大小
        :return:
        """
        for index in range(0, len(items), size):
            yield list(items[index:index + size])

    @staticmethod
    def _extract_text_content(message: dict[str, Any]) -> str:
        """
        提取 AI 返回文本

        :param message: AI 返回消息
        :return:
        """
        content = message.get('content')
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get('text')
                    if text:
                        parts.append(str(text))
            return '\n'.join(parts).strip()
        return ''

    @staticmethod
    def _extract_json_payload(content: str) -> dict[str, Any]:
        """
        从文本中提取 JSON

        :param content: 文本内容
        :return:
        """
        text = content.strip()
        if not text:
            raise errors.ServerError(msg='AI 返回内容为空')

        fenced_match = re.search(r'```json\s*(\{.*?\})\s*```', text, flags=re.DOTALL | re.IGNORECASE)
        if fenced_match:
            text = fenced_match.group(1)

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            start = text.find('{')
            end = text.rfind('}')
            if start < 0 or end < 0 or end <= start:
                raise errors.ServerError(msg='AI 返回格式异常，无法解析为 JSON')
            payload = json.loads(text[start:end + 1])

        if not isinstance(payload, dict):
            raise errors.ServerError(msg='AI 返回结构异常，期望为 JSON 对象')
        return payload

    @staticmethod
    def _extract_analysis(question: Question) -> QuestionAnalysis | None:
        """
        获取默认解析

        :param question: 题目
        :return:
        """
        if not question.analyses:
            return None

        return next((item for item in question.analyses if item.is_default), question.analyses[0])

    @classmethod
    def _normalize_reference_context(
        cls,
        *,
        question: Question,
        analysis: QuestionAnalysis | None,
        full_score: Decimal,
    ) -> dict[str, Any]:
        """
        提取参考判分上下文

        :param question: 题目
        :param analysis: 题目解析
        :param full_score: 满分
        :return:
        """
        answer_data = analysis.answer_data if analysis and analysis.answer_data else {}
        raw_correct = answer_data.get('correct')
        keywords = answer_data.get('keywords') or []
        rubric = answer_data.get('rubric') or answer_data.get('score_points') or []
        reference_answer = answer_data.get('reference_answer')
        if not reference_answer:
            reference_answer = raw_correct

        if isinstance(reference_answer, list):
            reference_answer = '；'.join(str(item).strip() for item in reference_answer if str(item).strip())
        elif isinstance(reference_answer, dict):
            reference_answer = json.dumps(reference_answer, ensure_ascii=False, sort_keys=True)
        elif reference_answer is not None:
            reference_answer = str(reference_answer).strip()

        analysis_text = cls._strip_html(analysis.content if analysis else '')
        stem_text = cls._strip_html(question.stem)
        normalized_keywords = [str(item).strip() for item in keywords if str(item).strip()]
        normalized_rubric = [str(item).strip() for item in rubric if str(item).strip()]
        has_reference = any([
            reference_answer and reference_answer not in PLACEHOLDER_TEXTS,
            normalized_keywords,
            normalized_rubric,
            analysis_text and analysis_text not in PLACEHOLDER_TEXTS,
        ])

        return {
            'stem_text': stem_text,
            'analysis_text': analysis_text,
            'reference_answer': reference_answer or None,
            'keywords': normalized_keywords,
            'rubric': normalized_rubric,
            'has_reference': has_reference,
            'full_score': str(full_score),
        }

    @staticmethod
    def _normalize_knowledge_points(question: Question) -> list[str]:
        """
        规范化知识点

        :param question: 题目
        :return:
        """
        values: list[str] = []
        raw_items = question.knowledge_point or []
        for item in raw_items:
            if isinstance(item, str):
                text = item.strip()
                if text:
                    values.append(text)
                continue
            if isinstance(item, dict):
                for key in ('name', 'label', 'title'):
                    text = item.get(key)
                    if text:
                        values.append(str(text).strip())
                        break
        return [item for item in values if item]

    @staticmethod
    async def _resolve_runtime_model(db: AsyncSession, *, model_name: str = AI_DEFAULT_MODEL_NAME) -> tuple[AIModel, AIProvider]:
        """
        获取可用 AI 模型和供应商

        :param db: 数据库会话
        :param model_name: 模型名称
        :return:
        """
        stmt = (
            select(AIModel, AIProvider)
            .join(AIProvider, AIProvider.id == AIModel.provider_id)
            .where(
                AIModel.model_id == model_name,
                AIModel.status == 1,
                AIProvider.status == 1,
            )
            .order_by(AIModel.id.desc())
        )
        result = await db.execute(stmt)
        row = result.first()
        if not row:
            raise errors.NotFoundError(msg=f'未找到可用的 AI 模型：{model_name}')
        return row[0], row[1]

    @classmethod
    def _build_question_eval_messages(cls, items: list[dict[str, Any]]) -> list[AIChatMessage]:
        """
        构建单题评估提示词

        :param items: 评估项
        :return:
        """
        system_prompt = (
            '你是温和但专业的中文考试阅卷助手。'
            '你只能依据题目、用户答案、参考答案、关键词、采分点和解析进行评分，'
            '不能编造参考信息。若参考信息不足，请返回 failed。'
            '请保持评分口径稳定，适当鼓励用户，但分数必须克制。'
            '你必须只返回 JSON，不要输出任何额外文字。'
        )
        user_prompt = (
            '请批量评估以下主观题作答，输出 JSON 对象，格式为：'
            '{"evaluations":[{"record_id":1,"status":"succeeded","score":8.5,"max_score":10,'
            '"confidence":0.86,"reference_answer":"...","grading_summary":"...",'
            '"strengths":["..."],"missing_points":["..."],"improvement_suggestions":["..."],'
            '"encouragement":"...","knowledge_points":["..."],"needs_manual_review":false,'
            '"failure_reason":null}]}\n'
            '若某题参考信息不足，status 返回 failed，score/max_score 仍保留满分，'
            '并在 failure_reason 中说明原因。\n'
            f'题目数据如下：\n{json.dumps(items, ensure_ascii=False)}'
        )
        return [
            AIChatMessage(role='system', content=system_prompt),
            AIChatMessage(role='user', content=user_prompt),
        ]

    @classmethod
    def _build_session_summary_messages(cls, payload: dict[str, Any]) -> list[AIChatMessage]:
        """
        构建会话总结提示词

        :param payload: 会话总结数据
        :return:
        """
        system_prompt = (
            '你是中文学习教练，请基于练习会话数据生成简洁、可信、可执行的总结。'
            '不要编造未提供的信息，语气鼓励但结论要稳。'
            '你必须只返回 JSON，不要输出任何额外文字。'
        )
        user_prompt = (
            '请根据以下练习会话数据生成 JSON，总结格式为：'
            '{"overview":"...","strengths":["..."],"high_frequency_issues":["..."],'
            '"weak_knowledge_points":[{"name":"...","reason":"..."}],'
            '"next_actions":["..."],"encouragement":"...","needs_manual_review":false}\n'
            f'会话数据如下：\n{json.dumps(payload, ensure_ascii=False)}'
        )
        return [
            AIChatMessage(role='system', content=system_prompt),
            AIChatMessage(role='user', content=user_prompt),
        ]

    @classmethod
    async def _invoke_json_chat(
        cls,
        *,
        db: AsyncSession,
        provider: AIProvider,
        model: AIModel,
        messages: list[AIChatMessage],
        max_tokens: int,
    ) -> dict[str, Any]:
        """
        调用 AI 并解析 JSON

        :param db: 数据库会话
        :param provider: AI 供应商
        :param model: AI 模型
        :param messages: 消息列表
        :param max_tokens: 输出 token 上限
        :return:
        """
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
        content = cls._extract_text_content(response)
        return cls._extract_json_payload(content)

    @classmethod
    async def _create_question_eval_failure(
        cls,
        *,
        db: AsyncSession,
        provider: AIProvider | None,
        model_name: str | None,
        record: PracticeRecord,
        trigger_source: str,
        prompt_version: str,
        full_score: Decimal,
        request_payload: dict[str, Any],
        error_message: str,
    ) -> PracticeAIEvaluation:
        """
        保存单题失败结果

        :param db: 数据库会话
        :param provider: AI 供应商
        :param model_name: 模型名称
        :param record: 作答记录
        :param trigger_source: 触发来源
        :param prompt_version: 提示词版本
        :param full_score: 满分
        :param request_payload: 请求快照
        :param error_message: 错误信息
        :return:
        """
        await practice_ai_evaluation_dao.mark_record_not_latest(db=db, practice_record_id=record.id)
        now = timezone.now()
        return await practice_ai_evaluation_dao.create(
            db=db,
            obj={
                'user_id': record.user_id,
                'session_id': record.session_id,
                'practice_record_id': record.id,
                'question_id': record.question_id,
                'target_type': 'question_eval',
                'trigger_source': trigger_source,
                'status': 'failed',
                'provider_id': provider.id if provider else None,
                'model_name': model_name,
                'prompt_version': prompt_version,
                'score': None,
                'max_score': full_score,
                'confidence': None,
                'summary_text': None,
                'request_payload': request_payload,
                'result_payload': None,
                'error_message': error_message,
                'started_at': now,
                'finished_at': now,
                'is_latest': True,
                'created_by': record.user_id,
            },
        )

    @classmethod
    async def evaluate_subjective_records(
        cls,
        *,
        db: AsyncSession,
        session: PracticeSession,
        records: Sequence[PracticeRecord],
        question_map: dict[int, Question],
        trigger_source: str,
        force_regenerate: bool,
        judge_version: str | None = None,
    ) -> dict[int, PracticeAIEvaluation]:
        """
        批量评估主观题作答

        :param db: 数据库会话
        :param session: 会话
        :param records: 作答记录
        :param question_map: 题目映射
        :param trigger_source: 触发来源
        :param force_regenerate: 是否强制重生成
        :param judge_version: 判题版本
        :return:
        """
        evaluation_map: dict[int, PracticeAIEvaluation] = {}
        subjective_records: list[PracticeRecord] = []

        for record in records:
            question = question_map.get(record.question_id)
            if not question or question.type not in SUBJECTIVE_QUESTION_TYPES:
                continue

            if not force_regenerate:
                latest = await practice_ai_evaluation_dao.get_latest_question_eval(
                    db=db,
                    practice_record_id=record.id,
                )
                if latest and latest.status == 'succeeded':
                    evaluation_map[record.id] = latest
                    continue

            subjective_records.append(record)

        if not subjective_records:
            return evaluation_map

        model, provider = await cls._resolve_runtime_model(db=db)
        prepared_items: list[dict[str, Any]] = []

        for record in subjective_records:
            question = question_map.get(record.question_id)
            if not question:
                continue

            analysis = cls._extract_analysis(question)
            reference_context = cls._normalize_reference_context(
                question=question,
                analysis=analysis,
                full_score=record.full_score,
            )
            request_payload = {
                'record_id': record.id,
                'question_id': question.id,
                'question_type': question.type,
                'full_score': str(record.full_score),
                'user_answer': cls._stringify_answer(record.user_answer),
                'reference_context': reference_context,
            }
            if not reference_context['has_reference']:
                evaluation_map[record.id] = await cls._create_question_eval_failure(
                    db=db,
                    provider=provider,
                    model_name=model.model_id,
                    record=record,
                    trigger_source=trigger_source,
                    prompt_version=QUESTION_EVAL_PROMPT_VERSION,
                    full_score=record.full_score,
                    request_payload=request_payload,
                    error_message='题目缺少可用的参考答案或解析，暂无法稳定进行 AI 判分',
                )
                continue

            prepared_items.append({
                'record': record,
                'request_payload': request_payload,
                'prompt_item': {
                    'record_id': record.id,
                    'question_id': question.id,
                    'question_type': question.type,
                    'full_score': str(record.full_score),
                    'knowledge_points': cls._normalize_knowledge_points(question),
                    'question_stem': reference_context['stem_text'],
                    'user_answer': cls._stringify_answer(record.user_answer),
                    'reference_answer': reference_context['reference_answer'],
                    'keywords': reference_context['keywords'],
                    'rubric': reference_context['rubric'],
                    'analysis': reference_context['analysis_text'],
                },
            })

        for chunk in cls._chunk_items(prepared_items, QUESTION_EVAL_CHUNK_SIZE):
            prompt_items = [item['prompt_item'] for item in chunk]
            started_at = timezone.now()
            payload = await cls._invoke_json_chat(
                db=db,
                provider=provider,
                model=model,
                messages=cls._build_question_eval_messages(prompt_items),
                max_tokens=2500,
            )
            finished_at = timezone.now()
            evaluations = payload.get('evaluations')
            if not isinstance(evaluations, list):
                raise errors.ServerError(msg='AI 判分返回格式异常，缺少 evaluations 列表')

            response_map: dict[int, dict[str, Any]] = {}
            for item in evaluations:
                if not isinstance(item, dict):
                    continue
                record_id = item.get('record_id')
                if isinstance(record_id, int):
                    response_map[record_id] = item

            for item in chunk:
                record = item['record']
                raw_result = response_map.get(record.id)
                if not raw_result:
                    evaluation_map[record.id] = await cls._create_question_eval_failure(
                        db=db,
                        provider=provider,
                        model_name=model.model_id,
                        record=record,
                        trigger_source=trigger_source,
                        prompt_version=QUESTION_EVAL_PROMPT_VERSION,
                        full_score=record.full_score,
                        request_payload=item['request_payload'],
                        error_message='AI 未返回该题评估结果',
                    )
                    continue

                status = str(raw_result.get('status') or 'succeeded').strip().lower()
                if status != 'succeeded':
                    evaluation_map[record.id] = await cls._create_question_eval_failure(
                        db=db,
                        provider=provider,
                        model_name=model.model_id,
                        record=record,
                        trigger_source=trigger_source,
                        prompt_version=QUESTION_EVAL_PROMPT_VERSION,
                        full_score=record.full_score,
                        request_payload=item['request_payload'],
                        error_message=str(raw_result.get('failure_reason') or 'AI 判分失败'),
                    )
                    continue

                score = cls._normalize_decimal(raw_result.get('score'))
                if score is None:
                    score = Decimal('0.00')
                max_score = cls._normalize_decimal(raw_result.get('max_score'))
                if max_score is None:
                    max_score = cls._normalize_decimal(record.full_score)
                if max_score is None or max_score <= Decimal('0'):
                    max_score = Decimal('1.00')
                if score < Decimal('0'):
                    score = Decimal('0.00')
                if score > max_score:
                    score = max_score

                confidence = cls._normalize_confidence(raw_result.get('confidence'))
                is_correct = score >= (max_score * QUESTION_EVAL_THRESHOLD)
                summary_text = str(raw_result.get('grading_summary') or '').strip() or None
                result_payload = {
                    'reference_answer': raw_result.get('reference_answer'),
                    'grading_summary': raw_result.get('grading_summary'),
                    'strengths': raw_result.get('strengths') or [],
                    'missing_points': raw_result.get('missing_points') or [],
                    'improvement_suggestions': raw_result.get('improvement_suggestions') or [],
                    'encouragement': raw_result.get('encouragement'),
                    'knowledge_points': raw_result.get('knowledge_points') or [],
                    'needs_manual_review': bool(raw_result.get('needs_manual_review')),
                    'judge_version': judge_version,
                }

                await practice_ai_evaluation_dao.mark_record_not_latest(db=db, practice_record_id=record.id)
                evaluation = await practice_ai_evaluation_dao.create(
                    db=db,
                    obj={
                        'user_id': record.user_id,
                        'session_id': record.session_id,
                        'practice_record_id': record.id,
                        'question_id': record.question_id,
                        'target_type': 'question_eval',
                        'trigger_source': trigger_source,
                        'status': 'succeeded',
                        'provider_id': provider.id,
                        'model_name': model.model_id,
                        'prompt_version': QUESTION_EVAL_PROMPT_VERSION,
                        'score': score,
                        'max_score': max_score,
                        'confidence': confidence,
                        'summary_text': summary_text,
                        'request_payload': item['request_payload'],
                        'result_payload': result_payload,
                        'error_message': None,
                        'started_at': started_at,
                        'finished_at': finished_at,
                        'is_latest': True,
                        'created_by': record.user_id,
                    },
                )
                await practice_record_dao.update_judge_result(
                    db=db,
                    record_id=record.id,
                    is_correct=is_correct,
                    score=score,
                    full_score=max_score,
                    judged_at=finished_at,
                    judge_version=judge_version or QUESTION_EVAL_PROMPT_VERSION,
                )
                evaluation_map[record.id] = evaluation

        return evaluation_map

    @classmethod
    async def _get_owned_record_with_question(
        cls,
        *,
        db: AsyncSession,
        record_id: int,
        user_id: int,
    ) -> tuple[PracticeRecord, PracticeSession, Question]:
        """
        获取用户作答记录及题目

        :param db: 数据库会话
        :param record_id: 作答记录 ID
        :param user_id: 用户 ID
        :return:
        """
        stmt = (
            select(PracticeRecord)
            .where(PracticeRecord.id == record_id)
            .options(
                selectinload(PracticeRecord.session),
                selectinload(PracticeRecord.question).selectinload(Question.analyses),
            )
        )
        result = await db.execute(stmt)
        record = result.scalars().first()
        if not record:
            raise errors.NotFoundError(msg='答题记录不存在')
        if record.user_id != user_id:
            raise errors.ForbiddenError(msg='无权访问此答题记录')
        if not record.session:
            raise errors.NotFoundError(msg='答题记录关联会话不存在')
        if not record.question:
            raise errors.NotFoundError(msg='答题记录关联题目不存在')
        return record, record.session, record.question

    @classmethod
    async def judge_record(
        cls,
        *,
        db: AsyncSession,
        record_id: int,
        user_id: int,
        force_regenerate: bool,
    ) -> PracticeAIEvaluation:
        """
        手动触发单题 AI 判分

        :param db: 数据库会话
        :param record_id: 作答记录 ID
        :param user_id: 用户 ID
        :param force_regenerate: 是否强制重生成
        :return:
        """
        record, session, question = await cls._get_owned_record_with_question(
            db=db,
            record_id=record_id,
            user_id=user_id,
        )
        if question.type not in SUBJECTIVE_QUESTION_TYPES:
            raise errors.RequestError(msg='当前题型不支持 AI 主观题判分')

        latest = await practice_ai_evaluation_dao.get_latest_question_eval(
            db=db,
            practice_record_id=record_id,
        )
        if latest and not force_regenerate:
            return latest

        if force_regenerate and session.status != 'in_progress':
            raise errors.ForbiddenError(msg='会话已提交，暂不支持重新 AI 判分')

        evaluation_map = await cls.evaluate_subjective_records(
            db=db,
            session=session,
            records=[record],
            question_map={question.id: question},
            trigger_source='manual',
            force_regenerate=True,
            judge_version=QUESTION_EVAL_PROMPT_VERSION,
        )
        evaluation = evaluation_map.get(record.id)
        if not evaluation:
            raise errors.ServerError(msg='AI 判分未生成结果')
        return evaluation

    @classmethod
    async def judge_session_subjective_records(
        cls,
        *,
        db: AsyncSession,
        session_id: int,
        user_id: int,
        force_regenerate: bool,
    ) -> list[PracticeAIEvaluation]:
        """
        手动触发会话主观题判分

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param user_id: 用户 ID
        :param force_regenerate: 是否强制重生成
        :return:
        """
        session = await practice_session_dao.get(db=db, session_id=session_id)
        if not session:
            raise errors.NotFoundError(msg='会话不存在')
        if session.user_id != user_id:
            raise errors.ForbiddenError(msg='无权访问此会话')
        if session.status != 'in_progress':
            raise errors.ForbiddenError(msg='会话已提交，暂不支持重新 AI 判分')

        records = await practice_record_dao.get_by_session(db=db, session_id=session_id)
        if not records:
            raise errors.NotFoundError(msg='当前会话暂无作答记录')

        question_ids = [record.question_id for record in records]
        stmt = (
            select(Question)
            .where(Question.id.in_(question_ids))
            .options(selectinload(Question.analyses))
        )
        result = await db.execute(stmt)
        question_map = {question.id: question for question in result.scalars().all()}

        evaluation_map = await cls.evaluate_subjective_records(
            db=db,
            session=session,
            records=records,
            question_map=question_map,
            trigger_source='manual',
            force_regenerate=force_regenerate,
            judge_version=QUESTION_EVAL_PROMPT_VERSION,
        )
        if not evaluation_map:
            raise errors.RequestError(msg='当前会话没有可判分的主观题记录')

        return sorted(
            evaluation_map.values(),
            key=lambda item: (item.practice_record_id or 0, item.id),
        )

    @classmethod
    async def get_latest_record_evaluation(
        cls,
        *,
        db: AsyncSession,
        record_id: int,
        user_id: int,
    ) -> PracticeAIEvaluation:
        """
        获取最新单题评估

        :param db: 数据库会话
        :param record_id: 作答记录 ID
        :param user_id: 用户 ID
        :return:
        """
        record, _, question = await cls._get_owned_record_with_question(
            db=db,
            record_id=record_id,
            user_id=user_id,
        )
        if question.type not in SUBJECTIVE_QUESTION_TYPES:
            raise errors.RequestError(msg='当前题型不支持 AI 主观题判分')

        evaluation = await practice_ai_evaluation_dao.get_latest_question_eval(
            db=db,
            practice_record_id=record.id,
        )
        if not evaluation:
            raise errors.NotFoundError(msg='该题暂无 AI 判分结果')
        return evaluation

    @classmethod
    async def generate_session_summary(
        cls,
        *,
        db: AsyncSession,
        session_id: int,
        user_id: int,
        force_regenerate: bool,
    ) -> PracticeAIEvaluation:
        """
        生成会话 AI 总结

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param user_id: 用户 ID
        :param force_regenerate: 是否强制重生成
        :return:
        """
        session_detail = await practice_session_dao.get_detail(db=db, session_id=session_id)
        if not session_detail:
            raise errors.NotFoundError(msg='会话不存在')
        if session_detail.user_id != user_id:
            raise errors.ForbiddenError(msg='无权访问此会话')
        if session_detail.status != 'completed':
            raise errors.ForbiddenError(msg='请先完成当前会话，再生成 AI 总结')

        latest = await practice_ai_evaluation_dao.get_latest_session_summary(db=db, session_id=session_id)
        if latest and not force_regenerate:
            return latest

        records = list(session_detail.records or [])
        if not records:
            raise errors.NotFoundError(msg='当前会话暂无作答记录')

        question_ids = [record.question_id for record in records]
        stmt = select(Question).where(Question.id.in_(question_ids))
        result = await db.execute(stmt)
        question_map = {question.id: question for question in result.scalars().all()}

        latest_evaluations = await practice_ai_evaluation_dao.list_latest_question_evals_by_session(
            db=db,
            session_id=session_id,
        )
        evaluation_map = {item.practice_record_id: item for item in latest_evaluations if item.practice_record_id is not None}

        model, provider = await cls._resolve_runtime_model(db=db)
        wrong_records = [item for item in records if item.is_correct is False]
        wrong_items: list[dict[str, Any]] = []
        for record in wrong_records[:50]:
            question = question_map.get(record.question_id)
            if not question:
                continue
            latest_eval = evaluation_map.get(record.id)
            eval_payload = latest_eval.result_payload if latest_eval and latest_eval.result_payload else {}
            wrong_items.append({
                'seq_no': record.seq_no,
                'question_id': record.question_id,
                'question_type': question.type,
                'score': str(record.score or Decimal('0')),
                'full_score': str(record.full_score),
                'knowledge_points': cls._normalize_knowledge_points(question),
                'question_preview': cls._strip_html(question.stem)[:200],
                'grading_summary': eval_payload.get('grading_summary'),
                'missing_points': eval_payload.get('missing_points') or [],
                'improvement_suggestions': eval_payload.get('improvement_suggestions') or [],
            })

        request_payload = {
            'session_id': session_detail.id,
            'session_type': session_detail.session_type,
            'total_count': session_detail.total_count,
            'completed_count': session_detail.completed_count,
            'correct_count': session_detail.correct_count,
            'wrong_count': session_detail.wrong_count,
            'accuracy_rate': str(session_detail.accuracy_rate),
            'score': str(session_detail.score or Decimal('0')),
            'total_score': str(session_detail.total_score or Decimal('0')),
            'wrong_items': wrong_items,
        }
        started_at = timezone.now()
        payload = await cls._invoke_json_chat(
            db=db,
            provider=provider,
            model=model,
            messages=cls._build_session_summary_messages(request_payload),
            max_tokens=2200,
        )
        finished_at = timezone.now()
        summary_text = str(payload.get('overview') or '').strip() or None
        result_payload = {
            'overview': payload.get('overview'),
            'strengths': payload.get('strengths') or [],
            'high_frequency_issues': payload.get('high_frequency_issues') or [],
            'weak_knowledge_points': payload.get('weak_knowledge_points') or [],
            'next_actions': payload.get('next_actions') or [],
            'encouragement': payload.get('encouragement'),
            'needs_manual_review': bool(payload.get('needs_manual_review')),
        }

        await practice_ai_evaluation_dao.mark_session_summary_not_latest(db=db, session_id=session_id)
        return await practice_ai_evaluation_dao.create(
            db=db,
            obj={
                'user_id': user_id,
                'session_id': session_id,
                'practice_record_id': None,
                'question_id': None,
                'target_type': 'session_summary',
                'trigger_source': 'manual',
                'status': 'succeeded',
                'provider_id': provider.id,
                'model_name': model.model_id,
                'prompt_version': SESSION_SUMMARY_PROMPT_VERSION,
                'score': session_detail.score,
                'max_score': session_detail.total_score,
                'confidence': None,
                'summary_text': summary_text,
                'request_payload': request_payload,
                'result_payload': result_payload,
                'error_message': None,
                'started_at': started_at,
                'finished_at': finished_at,
                'is_latest': True,
                'created_by': user_id,
            },
        )

    @classmethod
    async def get_latest_session_summary(
        cls,
        *,
        db: AsyncSession,
        session_id: int,
        user_id: int,
    ) -> PracticeAIEvaluation:
        """
        获取最新会话总结

        :param db: 数据库会话
        :param session_id: 会话 ID
        :param user_id: 用户 ID
        :return:
        """
        session = await practice_session_dao.get(db=db, session_id=session_id)
        if not session:
            raise errors.NotFoundError(msg='会话不存在')
        if session.user_id != user_id:
            raise errors.ForbiddenError(msg='无权访问此会话')

        evaluation = await practice_ai_evaluation_dao.get_latest_session_summary(db=db, session_id=session_id)
        if not evaluation:
            raise errors.NotFoundError(msg='当前会话暂无 AI 总结')
        return evaluation


practice_ai_evaluation_service: PracticeAIEvaluationService = PracticeAIEvaluationService()
