from __future__ import annotations

import json
import re
import time

from typing import TYPE_CHECKING, Any

from backend.plugin.agent.crud import agent_rubric_dao
from backend.plugin.agent.service.runtime.model_resolver import resolve_agent_model
from backend.plugin.agent.service.shenlun.answer_formatting import (
    build_revised_answer_retry_prompt,
    compact_revised_answer_linebreaks,
    normalize_revised_answer_word_count,
    revised_answer_word_count_status,
)
from backend.plugin.agent.service.shenlun.common import (
    ANSWER_GRID_RULES,
    MAX_MODEL_CALLS,
    PIPELINE_VERSION,
    RESULT_VERSION,
    RUBRIC_VERSION,
    clean,
    extract_word_limit,
    infer_question_type,
    stable_hash,
)
from backend.plugin.agent.service.shenlun.consensus import compact_reference_consensus
from backend.plugin.agent.service.shenlun.report import render_grading_report
from backend.plugin.agent.service.shenlun.rubric import normalize_references, validate_rubric
from backend.plugin.agent.service.shenlun.validation import validate_grading_result
from backend.plugin.ai.schema.chat import AIChat, AIChatMessage
from backend.plugin.ai.service.chat_service import ai_chat_service

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from backend.plugin.ai.model.model import AIModel
    from backend.plugin.ai.model.provider import AIProvider


def extract_json_payload(content: str, tag: str = '') -> dict[str, Any]:
    text = str(content or '').strip()
    if tag:
        match = re.search(rf'<{re.escape(tag)}>\s*(.*?)\s*</{re.escape(tag)}>', text, re.IGNORECASE | re.DOTALL)
        if match:
            text = match.group(1).strip()
    text = re.sub(r'^```(?:json)?\s*|\s*```$', '', text, flags=re.IGNORECASE | re.DOTALL).strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find('{'), text.rfind('}')
        if start < 0 or end <= start:
            raise ValueError('模型未返回合法 JSON') from None
        payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise TypeError('模型返回结果不是 JSON 对象')
    return payload


class ShenlunGradingPipeline:
    """YanShen 风格的可审计申论批改流水线。"""

    async def run(self, *, db: AsyncSession, payload: dict[str, Any], model_name: str | None = None) -> dict[str, Any]:
        calls: list[dict[str, Any]] = []
        stages: list[dict[str, Any]] = []
        question = clean(payload.get('question'), 10000)
        answer_text = str(payload.get('answer_text') or '').strip()
        max_score = float(payload.get('max_score') or 100)
        materials = payload.get('materials') if isinstance(payload.get('materials'), list) else []
        reference_context = (
            payload.get('reference_context') if isinstance(payload.get('reference_context'), dict) else {}
        )
        question_type = infer_question_type(question, reference_context)
        word_limit = extract_word_limit(question, reference_context.get('grading_config') or {})
        references = normalize_references(reference_context)
        consensus = compact_reference_consensus(references, materials)
        question_feedback = (
            payload.get('question_feedback') if isinstance(payload.get('question_feedback'), list) else []
        )
        history_evidence = payload.get('history_evidence') if isinstance(payload.get('history_evidence'), dict) else {}
        calibration_policy = (
            payload.get('calibration_policy') if isinstance(payload.get('calibration_policy'), dict) else None
        )
        similar_retrieval = (
            payload.get('similar_retrieval') if isinstance(payload.get('similar_retrieval'), dict) else {}
        )
        reference_set_hash = stable_hash(references)
        source_hash = stable_hash({
            'question': question,
            'materials': materials,
            'question_feedback': question_feedback,
            'rubric_precedents': [
                {
                    'question_id': item.get('question_id'),
                    'rubric_id': (item.get('rubric_precedent') or {}).get('rubric_id'),
                }
                for item in similar_retrieval.get('candidates') or []
                if item.get('rubric_precedent')
            ],
        })
        model: AIModel | None = None
        provider: AIProvider | None = None
        try:
            model, provider = await self._resolve_model(db=db, model_name=model_name)
            question_id = int(payload.get('question_id') or 0)
            cached = await agent_rubric_dao.get_ready(
                db,
                agent_key='shenlun.grading',
                question_id=question_id,
                reference_set_hash=reference_set_hash,
                source_hash=source_hash,
                rubric_version=RUBRIC_VERSION,
            )
            cache_target = None
            if (
                cached is not None
                and (cached.rubric_payload or {}).get('points')
                and (cached.rubric_payload or {}).get('dimensions')
            ):
                rubric = dict(cached.rubric_payload or {})
                stages.append({'node_key': 'rubric_reuser', 'status': 'succeeded', 'cache_id': cached.id})
            else:
                cache_target = cached
                rubric_raw = await self._call(
                    db=db,
                    model=model,
                    provider=provider,
                    purpose='rubric_builder',
                    calls=calls,
                    prompt=self._rubric_prompt(
                        payload,
                        question_type,
                        question,
                        word_limit,
                        materials,
                        references,
                        consensus,
                        question_feedback,
                        similar_retrieval,
                    ),
                )
                try:
                    rubric = validate_rubric(
                        rubric_raw,
                        question_id=question_id,
                        question_type=question_type,
                        max_score=max_score,
                        word_limit=word_limit,
                        materials=materials,
                        references=references,
                    )
                except (TypeError, ValueError) as exc:
                    repaired = await self._call(
                        db=db,
                        model=model,
                        provider=provider,
                        purpose='rubric_repair',
                        calls=calls,
                        prompt=self._repair_prompt('评分基准', rubric_raw, str(exc)),
                    )
                    rubric = validate_rubric(
                        repaired,
                        question_id=question_id,
                        question_type=question_type,
                        max_score=max_score,
                        word_limit=word_limit,
                        materials=materials,
                        references=references,
                    )
                if cache_target is not None:
                    cache_target.status = 'ready'
                    cache_target.provider = provider.name
                    cache_target.model_name = model.model_id
                    cache_target.rubric_payload = rubric
                    cache_target.error_message = None
                    await db.flush()
                else:
                    await agent_rubric_dao.create_cache(
                        db,
                        data={
                            'agent_key': 'shenlun.grading',
                            'question_id': question_id,
                            'reference_set_hash': reference_set_hash,
                            'source_hash': source_hash,
                            'rubric_version': RUBRIC_VERSION,
                            'status': 'ready',
                            'provider': provider.name,
                            'model_name': model.model_id,
                            'rubric_payload': rubric,
                        },
                    )
            grading_prompt = self._grading_prompt(question, materials, answer_text, rubric, history_evidence)
            grading_raw = await self._call(
                db=db,
                model=model,
                provider=provider,
                purpose='grading',
                calls=calls,
                prompt=grading_prompt,
            )
            grading_evaluation = grading_raw
            try:
                result = validate_grading_result(
                    grading_evaluation,
                    rubric=rubric,
                    answer_text=answer_text,
                    evidence=history_evidence.get('evidence') or [],
                    calibration_policy=calibration_policy,
                )
            except (TypeError, ValueError) as exc:
                repaired = await self._call(
                    db=db,
                    model=model,
                    provider=provider,
                    purpose='grading_repair',
                    calls=calls,
                    prompt=self._repair_prompt('批改结果', grading_raw, str(exc)),
                )
                grading_evaluation = repaired
                result = validate_grading_result(
                    grading_evaluation,
                    rubric=rubric,
                    answer_text=answer_text,
                    evidence=history_evidence.get('evidence') or [],
                    calibration_policy=calibration_policy,
                )
            if result['review']['triggered'] and len(calls) < MAX_MODEL_CALLS:
                reviewed = await self._call(
                    db=db,
                    model=model,
                    provider=provider,
                    purpose='independent_review',
                    calls=calls,
                    prompt=self._review_prompt(question, answer_text, rubric, result),
                )
                reviewed_result = validate_grading_result(
                    self._merge_review_evaluation(grading_evaluation, reviewed),
                    rubric=rubric,
                    answer_text=answer_text,
                    evidence=history_evidence.get('evidence') or [],
                    calibration_policy=calibration_policy,
                    reviewed=True,
                )
                result = self._merge_review_result(result, reviewed_result)
            result['revised_answer'] = compact_revised_answer_linebreaks(result.get('revised_answer') or '', word_limit)
            report_markdown = normalize_revised_answer_word_count(render_grading_report(result, rubric), word_limit)
            word_count_status = revised_answer_word_count_status(report_markdown, word_limit)
            if word_count_status['over_limit'] and len(calls) < MAX_MODEL_CALLS:
                compressed = await self._call(
                    db=db,
                    model=model,
                    provider=provider,
                    purpose='revised_answer_compression',
                    calls=calls,
                    prompt=build_revised_answer_retry_prompt(grading_prompt, report_markdown, word_limit),
                )
                revised_answer = str(compressed.get('revised_answer') or '').strip()
                if revised_answer:
                    result['revised_answer'] = compact_revised_answer_linebreaks(revised_answer, word_limit)
                    report_markdown = normalize_revised_answer_word_count(
                        render_grading_report(result, rubric), word_limit
                    )
                    word_count_status = revised_answer_word_count_status(report_markdown, word_limit)
            pipeline_steps = [
                *stages,
                *[
                    {
                        'node_key': call['purpose'],
                        'status': 'succeeded',
                        'duration_ms': call['duration_ms'],
                    }
                    for call in calls
                ],
                {'node_key': 'validation', 'status': 'succeeded'},
                {'node_key': 'report_renderer', 'status': 'succeeded'},
            ]
            result.update({
                'rubric': rubric,
                'report_markdown': report_markdown,
                'word_count_status': word_count_status,
                'history_meta': {key: value for key, value in history_evidence.items() if key != 'evidence'},
                'personalization_evidence': history_evidence.get('evidence') or [],
                'similar_retrieval': similar_retrieval,
                'calibration_policy': calibration_policy
                or {
                    'policy_version': 'exam-anchor-calibration-v1',
                    'enabled': False,
                    'reason': 'activation_gate_not_met',
                },
                'pipeline_version': PIPELINE_VERSION,
                'model': {'provider': provider.name, 'model_name': model.model_id},
                'api_calls': calls,
                'pipeline_steps': pipeline_steps,
                'audit': {
                    'question_hash': stable_hash(question),
                    'answer_hash': stable_hash(answer_text),
                    'reference_set_hash': stable_hash(references),
                    'material_set_hash': stable_hash(materials),
                },
            })
            return result  # noqa: TRY300
        except Exception as exc:
            return self._fallback(
                question_type=question_type,
                max_score=max_score,
                word_limit=word_limit,
                answer_text=answer_text,
                error=exc,
                calls=calls,
                model=model,
                provider=provider,
            )

    @staticmethod
    async def _resolve_model(*, db: AsyncSession, model_name: str | None) -> tuple[AIModel, AIProvider]:
        return await resolve_agent_model(db=db, model_name=model_name)

    async def _call(
        self,
        *,
        db: AsyncSession,
        model: AIModel,
        provider: AIProvider,
        purpose: str,
        prompt: str,
        calls: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if len(calls) >= MAX_MODEL_CALLS:
            raise RuntimeError('模型调用次数已达到工作流上限')
        started = time.perf_counter()
        response = await ai_chat_service.raw_chat(
            db=db,
            chat=AIChat(
                provider_id=provider.id,
                model_id=model.model_id,
                messages=[
                    AIChatMessage(role='system', content='你是严谨的申论阅卷专家。只返回合法 JSON。'),
                    AIChatMessage(role='user', content=prompt),
                ],
                temperature=0.1,
                max_tokens=14000,
                seed=7,
                extra_body={'response_format': {'type': 'json_object'}},
            ),
        )
        content = response.get('content') if isinstance(response, dict) else response
        calls.append({
            'purpose': purpose,
            'duration_ms': int((time.perf_counter() - started) * 1000),
            'prompt_hash': stable_hash(prompt),
            'response_hash': stable_hash(content),
        })
        return extract_json_payload(content if isinstance(content, str) else json.dumps(content, ensure_ascii=False))

    @staticmethod
    def _rubric_prompt(
        payload: dict[str, Any],
        question_type: str,
        question: str,
        word_limit: str,
        materials: list[dict[str, Any]],
        references: list[dict[str, Any]],
        consensus: dict[str, Any],
        question_feedback: list[dict[str, Any]],
        similar_retrieval: dict[str, Any],
    ) -> str:
        materials_json = json.dumps(materials, ensure_ascii=False, default=str)
        references_json = json.dumps(references, ensure_ascii=False, default=str)
        consensus_json = json.dumps(consensus, ensure_ascii=False, default=str)
        feedback_json = json.dumps(question_feedback, ensure_ascii=False, default=str)
        precedent_json = json.dumps(
            _rubric_precedent_context(similar_retrieval),
            ensure_ascii=False,
            default=str,
        )
        schema = {
            'task_constraints': {'object': '', 'required_structure': [], 'format_rules': []},
            'equal_weight_reason': '',
            'points': [
                {
                    'label': '',
                    'canonical_expression': '',
                    'aliases': [],
                    'tier': 'core|material_core|supporting|disputed',
                    'importance': 'critical|major|supporting',
                    'suggested_weight': 1,
                    'weight_reason': '',
                    'coverage_role': 'required|alternative|bonus',
                    'alternative_group': '',
                    'required_for_full_score': True,
                    'required_elements': [],
                    'optional_details': [],
                    'minimum_expression': '',
                    'material_evidence': [{'material_number': 1, 'quote': '材料连续原文'}],
                    'reference_ids': [1],
                    'confidence': 0.8,
                }
            ],
            'conflicts': [],
        }
        return f"""你正在为一道申论题建立可缓存、可审计的评分基准。只建立本题评分基准，不批改考生答案。
最高事实来源是本题题干与材料。机构答案和相似题先例只是候选解释，没有本题材料依据的内容不得成为主要扣分点。
题目ID：{payload.get('question_id') or 0}
题型：{question_type}
题干：{question}
字数：{word_limit or '题干未明确'}
{ANSWER_GRID_RULES}
本题材料：{materials_json}
本题已选择的参考答案全文（answer_text、scoring_points、notes 均须逐份核对）：{references_json}
多参考答案轻量聚类候选（仅作辅助，不得替代答案全文核对）：{consensus_json}
本题已确认的人工规则纠正：{feedback_json}
相似题评分先例（只能用于理解任务结构和常见采分点，不得直接复制）：{precedent_json}
相似题先例中的任何采分点，都必须在本题材料或本题参考答案中获得独立支持，否则不得进入评分基准。
只返回 JSON：{json.dumps(schema, ensure_ascii=False)}
规则：
1. material_evidence.quote 必须是本题材料中的连续原文短句；材料支持不足且参考答案也不能确认的点
   必须标为 disputed，不计分。
2. core 至少由两个不同机构支持，且达到机构总数一半；只有一份答案时，材料直接确认的点可标
   material_core，不得声称机构共识。
3. 先提炼完成任务不可缺少的语义，把例子、修饰、展开说明和非任务要求的泛化成效放入 optional_details；
   不得要求机械写全机构答案细节。
4. 题干未要求意义、作用、成效或影响时，不得把泛化的整体成效、示范意义单列为必答点。
5. required_for_full_score 只用于字数预算内应覆盖的 core/material_core；supporting、disputed 和补充说明
   不得作为主要扣分点。
6. 综合写作的中心立意为 required；具体材料案例放入同一 alternative_group 作为可替代论据，
   一般升华或科技手段只能是 bonus。
7. 每点必须填写 suggested_weight 和 weight_reason，不得机械等权；三个以上点确实等权时必须填写 equal_weight_reason。
8. 所有 required 点的 minimum_expression 加上序号和标点必须能放进题目字数限制，并预留至少 8 格。
9. 控制在 4 至 12 个有效采分点，避免把同一措施、机制拆成细碎扣分项。
10. 只返回上述 JSON，不输出 Markdown、解释或考生答案。"""

    @staticmethod
    def _grading_prompt(
        question: str,
        materials: list[dict[str, Any]],
        answer_text: str,
        rubric: dict[str, Any],
        history_evidence: dict[str, Any],
    ) -> str:
        dimensions = [
            {'dimension': item['dimension'], 'max_score': item['weight'], 'score': 0, 'reason': ''}
            for item in rubric['dimensions']
        ]
        schema = {
            'point_matches': [
                {
                    'point_key': '',
                    'status': 'hit|partial|miss',
                    'coverage_ratio': 0.5,
                    'answer_quote': '答案连续原文',
                    'reason': '',
                    'confidence': 0.8,
                    'missing_elements': [],
                }
            ],
            'dimension_scores': dimensions,
            'annotations': [],
            'reference_fusion': '',
            'material_reading': [],
            'optimization_suggestions': [],
            'personalized_findings': [
                {
                    'finding': '',
                    'root_cause': '',
                    'next_step': '',
                    'evidence_ids': [],
                    'confidence': 'stage|recurring',
                }
            ],
            'overall_summary': '',
            'summary': {'verdict': '', 'strengths': [], 'weaknesses': []},
            'holistic_adjustment_reason': '',
            'revised_answer': '',
        }
        return f"""你正在使用已校验的不等权评分基准执行申论综合批改。先分析全部采分点，再按固定维度综合评分。
评分只能依据本题题干、材料、参考答案和评分基准；历史证据只用于个性化诊断和建议，不得改变采分点状态或维度得分。
题干：{question}
材料：{json.dumps(materials, ensure_ascii=False, default=str)}
评分基准：{json.dumps(rubric, ensure_ascii=False, default=str)}
考生答案：{answer_text}
历史批改证据：{json.dumps(history_evidence, ensure_ascii=False, default=str)}
维度分采用从 0 分向上给分的考场得分制，不是从满分起步的扣分制。普通“写到了”不能进入 90% 以上；
高于 80% 的维度必须有具体高分证据。
综合写作必须先判断整篇档位再分配维度分；语言流畅、标题完整和分段清楚本身不足以进入优秀档，
存在事实偏差、材料误读或主要论证空泛时通常不得给到 80 分以上。
只返回 JSON：{json.dumps(schema, ensure_ascii=False)}
规则：
1. 每个可计分 point_key 必须且只能出现一次，并逐字复制评分基准中的 point_key。
2. hit 固定 coverage_ratio=1，miss 固定为 0；partial 按 required_elements 实际覆盖比例给 0.1 至 0.9，
   不得机械全部写 0.5。
3. hit/partial 必须提供考生答案中的短连续原文；语义散落多处时可用“……”连接按原文顺序出现的短片段。
4. dimension_scores 必须逐项覆盖固定维度，score 在 0 到 max_score 之间；同一问题只在最相关维度扣一次。
5. point_based 的内容分最终由系统按必答点证据重算；holistic_essay 整体评价立意、材料转化和论证质量，
   不得因没用某一具体案例直接判核心任务失败。
6. annotations 除 add 外 quote 必须为原文连续片段；add 必须提供可精确定位的 anchor，并将拟补文字写入 replacement。
7. personalized_findings 只能引用 role=personalization 的真实 evidence_id；至少两次历史作答才能标 recurring，
   否则只能标 stage，并需写清现象、根因和下一步训练动作。
8. 修改版答案必须低于硬上限并预留至少 8 格，不得为写全 optional_details 挤占 required 点。
9. summary 和 overall_summary 不得输出总分、等级或分数算式，系统会自行汇总和缩放分数。
10. 只返回完整 JSON，不输出 Markdown 或额外解释。"""

    @staticmethod
    def _repair_prompt(kind: str, payload: dict[str, Any], error: str) -> str:
        raw_json = json.dumps(payload, ensure_ascii=False, default=str)
        return (
            f'修复以下{kind} JSON。只修复格式或校验指出的问题，不改变材料事实、评分判断或正文。\n'
            f'校验错误：{error}\n原 JSON：{raw_json}\n只返回完整合法 JSON，不要输出 Markdown。'
        )

    @staticmethod
    def _review_prompt(question: str, answer_text: str, rubric: dict[str, Any], result: dict[str, Any]) -> str:
        rubric_json = json.dumps(rubric, ensure_ascii=False, default=str)
        result_json = json.dumps(result, ensure_ascii=False, default=str)
        return (
            '你正在复核一份申论智能评分中的结构化冲突。只纠正采分点状态、证据短引文和维度分，'
            '不得重写点评、摘要或修改版答案。\n'
            f'题干：{question}\n答案：{answer_text}\n评分基准：{rubric_json}\n待复核结果：{result_json}\n'
            '每个 point_key 和维度必须且只能出现一次；不得输出总分；空格、标点、引号或省略号差异不得把已有语义\n'
            '改判为未命中。只返回包含 evaluation 的完整 JSON，evaluation 仅包含 point_matches、dimension_scores、\n'
            'holistic_adjustment_reason。'
        )

    @staticmethod
    def _merge_review_evaluation(original: dict[str, Any], reviewed: dict[str, Any]) -> dict[str, Any]:
        if isinstance(reviewed.get('evaluation'), dict):
            reviewed = reviewed['evaluation']
        merged = dict(original or {})
        for key in ('point_matches', 'dimension_scores', 'holistic_adjustment_reason'):
            if reviewed.get(key) is not None:
                merged[key] = reviewed[key]
        return merged

    @staticmethod
    def _merge_review_result(original: dict[str, Any], reviewed: dict[str, Any]) -> dict[str, Any]:
        merged = dict(original)
        for key in (
            'score_status',
            'status',
            'score',
            'display_score',
            'raw_score',
            'max_score',
            'display_max_score',
            'score_is_estimated',
            'point_matches',
            'dimension_scores',
            'weighted_coverage_score',
            'display_weighted_coverage_score',
            'content_score',
            'display_content_score',
            'score_calibration',
            'holistic_adjustment_reason',
            'review',
            'validation_errors',
            'quality_check',
        ):
            merged[key] = reviewed[key]
        return merged

    @staticmethod
    def _fallback(
        *,
        question_type: str,
        max_score: float,
        word_limit: str,
        answer_text: str,
        error: Exception,
        calls: list[dict[str, Any]],
        model: AIModel | None,
        provider: AIProvider | None,
    ) -> dict[str, Any]:
        result = {
            'schema_version': RESULT_VERSION,
            'status': 'fallback',
            'score_status': 'provisional',
            'question_type': question_type,
            'word_limit': word_limit,
            'score': 0.0,
            'raw_score': 0.0,
            'display_score': 0.0,
            'max_score': 100.0,
            'display_max_score': max_score,
            'score_is_estimated': False,
            'answer_word_count': len(answer_text),
            'point_matches': [],
            'dimension_scores': [],
            'weighted_coverage_score': 0.0,
            'content_score': 0.0,
            'display_weighted_coverage_score': 0.0,
            'display_content_score': 0.0,
            'score_calibration': {
                'policy_version': 'exam-anchor-calibration-v1',
                'raw_score': 0.0,
                'adjustment': 0.0,
                'anchor_count': 0,
                'enabled': False,
                'reason': 'pipeline_fallback',
            },
            'annotations': [],
            'material_reading': [],
            'optimization_suggestions': ['模型或评分基准暂不可用，请稍后重试完整批改。'],
            'overall_summary': '本次未完成可审计批改，未生成正式分数。',
            'summary': {'verdict': '本次未完成可审计批改，未生成正式分数。'},
            'revised_answer': '',
            'review': {'triggered': True, 'reasons': [type(error).__name__], 'decision': 'required'},
            'validation_errors': [str(error)[:500]],
            'quality_check': {'passed': False, 'notes': [str(error)[:500]]},
            'pipeline_version': PIPELINE_VERSION,
            'api_calls': calls,
            'pipeline_steps': [
                *[
                    {
                        'node_key': call['purpose'],
                        'status': 'succeeded',
                        'duration_ms': call['duration_ms'],
                    }
                    for call in calls
                ],
                {'node_key': 'pipeline_fallback', 'status': 'failed', 'error': type(error).__name__},
            ],
            'model': {'provider': provider.name if provider else '', 'model_name': model.model_id if model else ''},
        }
        result['report_markdown'] = '\n'.join([
            '## 总体评分',
            f'- 总分：0/{max_score:g}',
            '- 状态：本次未完成可审计批改，未生成正式分数。',
            '',
            '## 优化建议',
            '1. 请稍后重试完整批改。',
        ])
        return result


shenlun_grading_pipeline = ShenlunGradingPipeline()
_json_payload = extract_json_payload


def _rubric_precedent_context(retrieval: dict[str, Any]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for item in retrieval.get('candidates') or []:
        precedent = item.get('rubric_precedent') if isinstance(item.get('rubric_precedent'), dict) else None
        if precedent is None:
            continue
        output.append({
            'evidence_id': item.get('evidence_id'),
            'question_id': item.get('question_id'),
            'similarity': item.get('similarity'),
            'stem_preview': item.get('stem_preview'),
            'rubric_precedent': precedent,
        })
    return output[:5]


def _stringify(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if value is None:
        return ''
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    return str(value).strip()


def _resolve_quote(quote: str, answer: str) -> tuple[str, list[dict[str, Any]], str]:
    from backend.plugin.agent.service.shenlun.evidence_resolution import resolve_answer_evidence

    resolved = resolve_answer_evidence(quote, answer)
    return resolved.get('quote', quote), resolved.get('spans', []), resolved.get('status', 'unresolved')


def _deterministic_points(references: list[str], materials: list[dict[str, Any]]) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for text in references:
        for clause in re.split(r'[。；;\n]', str(text)):
            clause = clean(clause, 100)
            if len(re.sub(r'[^\u4e00-\u9fffA-Za-z0-9]', '', clause)) < 6:
                continue
            if any(item['canonical_expression'] == clause for item in points):
                continue
            matched = next((clause for material in materials if clause[:12] in str(material.get('content') or '')), '')
            points.append({
                'point_key': f'point-{len(points) + 1}',
                'label': clause[:40],
                'canonical_expression': clause,
                'tier': 'material_core' if matched else 'supporting',
                'importance': 'major',
                'weight': 1.0,
                'suggested_weight': 1.0,
                'required_for_full_score': bool(matched),
                'required_elements': [clause],
                'material_evidence': [{'quote': matched}] if matched else [],
            })
            if len(points) >= 12:
                return points
    return points
