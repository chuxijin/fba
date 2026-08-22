import asyncio

from decimal import Decimal

from backend.plugin.agent.service.adapter.qbank_v2_adapter import QbankV2Adapter, ShenlunAttemptInput
from backend.plugin.agent.service.runtime.events import AgentEventBus
from backend.plugin.agent.service.shenlun.answer_formatting import (
    answer_grid_metrics,
    normalize_revised_answer_word_count,
    revised_answer_word_count_status,
)
from backend.plugin.agent.service.shenlun.calibration import apply_score_calibration, fit_offset_policy
from backend.plugin.agent.service.shenlun.calibration_service import ShenlunCalibrationService, _percent
from backend.plugin.agent.service.shenlun.consensus import compact_reference_consensus
from backend.plugin.agent.service.shenlun.pipeline import (
    ShenlunGradingPipeline,
    _deterministic_points,
    _json_payload,
    _resolve_quote,
    _rubric_precedent_context,
    _stringify,
)
from backend.plugin.agent.service.shenlun.report import render_grading_report
from backend.plugin.agent.service.shenlun.semantic import embed_text, lexical_similarity
from backend.plugin.agent.service.shenlun.similar import ShenlunSimilarQuestionRetriever
from backend.plugin.agent.service.shenlun.validation import validate_grading_result


def test_extract_json_payload() -> None:
    payload = _json_payload('<smart_grading_json>{"evaluation": {}}</smart_grading_json>')
    assert payload == {'evaluation': {}}


def test_resolve_exact_answer_quote() -> None:
    quote, spans, status = _resolve_quote('完善基层服务', '应当完善基层服务，回应群众诉求。')
    assert quote == '完善基层服务'
    assert status == 'resolved'
    assert spans[0]['start'] == 2


def test_build_deterministic_points_from_reference() -> None:
    points = _deterministic_points(
        ['一是完善基层公共服务。二是健全群众诉求反馈机制。'],
        [{'content': '各地持续完善基层公共服务，及时回应群众诉求。'}],
    )
    assert points
    assert points[0]['point_key'] == 'point-1'


def test_stringify_structured_answer() -> None:
    assert _stringify({'text': '答案'}) == '{"text": "答案"}'


def test_qbank_html_clean() -> None:
    assert QbankV2Adapter.clean('<p>材料一<br>内容</p>') == '材料一 内容'


def test_attempt_input_stringify() -> None:
    assert ShenlunAttemptInput.stringify(['甲', '乙']) == '["甲", "乙"]'


def test_answer_grid_counts_line_break_as_remaining_cells() -> None:
    assert answer_grid_metrics('甲\n乙', columns=25)['occupied_cells'] == 26


def test_revised_answer_report_contains_word_limit_status() -> None:
    report = normalize_revised_answer_word_count('## 修改版答案\n\n甲乙丙', '3字以内')
    status = revised_answer_word_count_status(report, '3字以内')
    assert '实际字数：3字' in report
    assert status['over_limit'] is True


def test_independent_review_only_replaces_scoring_fields() -> None:
    merged = ShenlunGradingPipeline._merge_review_evaluation(
        {'point_matches': [{'point_key': 'a'}], 'overall_summary': '保留原总评', 'revised_answer': '保留原改写'},
        {'point_matches': [{'point_key': 'a', 'status': 'miss'}], 'dimension_scores': []},
    )
    assert merged['point_matches'][0]['status'] == 'miss'
    assert merged['overall_summary'] == '保留原总评'
    assert merged['revised_answer'] == '保留原改写'


def test_reference_consensus_keeps_source_traceability() -> None:
    consensus = compact_reference_consensus(
        [
            {'id': 1, 'organization': '甲', 'answer_text': '完善基层公共服务，回应群众诉求'},
            {'id': 2, 'organization': '乙', 'answer_text': '完善基层公共服务，及时回应群众诉求'},
        ],
        [{'material_number': 1, 'content': '各地持续完善基层公共服务，及时回应群众诉求。'}],
    )
    assert consensus['source_clause_count'] == 2
    assert consensus['clusters'][0]['reference_ids']
    assert consensus['clusters'][0]['material_candidate']['material_number'] == 1


def test_calibration_is_disabled_without_enough_cross_paper_anchors() -> None:
    policy = fit_offset_policy([{'paper_id': 1, 'actual_score': 70, 'predicted_score': 72}])
    score, audit = apply_score_calibration(72, policy)
    assert score == 72
    assert audit['enabled'] is False


def test_calibration_rejects_unsupported_policy_version() -> None:
    score, audit = apply_score_calibration(
        80,
        {'policy_version': 'unknown', 'enabled': True, 'offset': 3, 'max_adjustment': 3},
    )
    assert score == 80
    assert audit['reason'] == 'unsupported_policy_version'


def test_calibration_activates_only_after_cross_paper_validation() -> None:
    policy = fit_offset_policy([
        {'paper_id': 1, 'actual_score': 76, 'predicted_score': 80},
        {'paper_id': 2, 'actual_score': 72, 'predicted_score': 76},
        {'paper_id': 3, 'actual_score': 68, 'predicted_score': 72},
        {'paper_id': 4, 'actual_score': 80, 'predicted_score': 84},
    ])
    assert policy['enabled'] is True
    assert policy['paper_count'] == 4
    assert policy['calibrated_mae'] < policy['baseline_mae']


def test_calibration_percent_aggregation() -> None:
    assert _percent(Decimal(63), Decimal(70)) == Decimal(90)


def test_provisional_agent_run_is_not_a_calibration_prediction() -> None:
    class Run:
        status = 'succeeded'
        result_payload = {
            'status': 'provisional',
            'score_status': 'provisional',
            'raw_score': 80,
            'display_max_score': 20,
        }

    assert ShenlunCalibrationService._is_valid_agent_run(Run()) is False


def test_semantic_fallback_prefers_related_shenlun_text() -> None:
    query, _ = embed_text('归纳基层治理存在的问题并概括原因')
    related, _ = embed_text('概括基层治理中的主要问题及其原因')
    unrelated, _ = embed_text('写一篇关于科技创新的议论文')
    assert sum(a * b for a, b in zip(query, related)) > sum(a * b for a, b in zip(query, unrelated))
    assert lexical_similarity('基层治理问题', '概括基层治理主要问题') > lexical_similarity('基层治理问题', '科技创新')


def test_similar_retrieval_rejects_degraded_input() -> None:
    result = ShenlunSimilarQuestionRetriever._degraded(question_type='归纳概括', error=RuntimeError('x'))
    assert result['retrieval_degraded'] is True
    assert result['candidates'] == []


def test_rubric_precedent_prompt_excludes_grading_cases() -> None:
    context = _rubric_precedent_context({
        'candidates': [
            {
                'evidence_id': 'similar-question:1',
                'question_id': 1,
                'similarity': 0.8,
                'stem_preview': '概括问题',
                'rubric_precedent': {'rubric_id': 2, 'points': []},
                'grading_case': {'display_score': 18},
            }
        ]
    })
    assert context[0]['rubric_precedent']['rubric_id'] == 2
    assert 'grading_case' not in context[0]


def test_agent_event_bus_replays_terminal_event_to_late_subscriber() -> None:
    async def scenario() -> str:
        bus = AgentEventBus()
        await bus.publish(7, {'run_id': 7, 'status': 'succeeded'})
        stream = bus.stream(7)
        return await anext(stream)

    event = asyncio.run(scenario())
    assert '"status": "succeeded"' in event


def test_validation_uses_percent_score_and_actual_display_score() -> None:
    rubric = {
        'max_score': 100,
        'display_max_score': 20,
        'question_type': '归纳概括',
        'scoring_mode': 'point_based',
        'points': [
            {
                'point_key': 'point-1',
                'weight': 70,
                'importance': 'critical',
                'coverage_role': 'required',
                'label': '完善服务',
            }
        ],
        'dimensions': [
            {'dimension': 'content', 'label': '内容', 'weight': 70},
            {'dimension': 'structure', 'label': '结构', 'weight': 15},
            {'dimension': 'expression', 'label': '表达', 'weight': 10},
            {'dimension': 'format', 'label': '格式', 'weight': 5},
        ],
    }
    result = validate_grading_result(
        {
            'point_matches': [
                {'point_key': 'point-1', 'status': 'hit', 'coverage_ratio': 1, 'answer_quote': '完善服务'}
            ],
            'dimension_scores': [
                {'dimension': 'content', 'score': 70},
                {'dimension': 'structure', 'score': 10},
                {'dimension': 'expression', 'score': 8},
                {'dimension': 'format', 'score': 4},
            ],
        },
        rubric=rubric,
        answer_text='完善服务',
    )
    assert result['score'] == 92
    assert abs(result['display_score'] - 18.4) < 0.001
    assert result['display_content_score'] == 14


def test_personalized_findings_require_real_evidence_ids() -> None:
    rubric = {
        'max_score': 100,
        'display_max_score': 100,
        'question_type': '归纳概括',
        'scoring_mode': 'point_based',
        'points': [],
        'dimensions': [{'dimension': 'content', 'label': '内容', 'weight': 100}],
    }
    result = validate_grading_result(
        {
            'point_matches': [],
            'dimension_scores': [{'dimension': 'content', 'score': 50}],
            'personalized_findings': [
                {
                    'finding': '多次篇幅偏短',
                    'evidence_ids': ['attempt:1', 'fake:2'],
                    'confidence': 'recurring',
                }
            ],
        },
        rubric=rubric,
        answer_text='作答',
        evidence=[{'evidence_id': 'attempt:1', 'attempt_id': 1, 'role': 'personalization'}],
    )
    finding = result['personalized_findings'][0]
    assert finding['evidence_ids'] == ['attempt:1']
    assert finding['confidence'] == 'stage'


def test_report_removes_model_score_from_overall_summary() -> None:
    report = render_grading_report(
        {
            'display_score': 15,
            'display_max_score': 20,
            'score': 75,
            'summary': {'verdict': '总分：99分。主体任务完成较好。'},
            'point_matches': [],
            'dimension_scores': [],
        },
        {'max_score': 100, 'dimensions': [], 'points': []},
    )
    assert '总分：99分' not in report
    assert '主体任务完成较好' in report


def test_existing_references_override_no_reference_claim() -> None:
    rubric = {
        'max_score': 100,
        'display_max_score': 100,
        'question_type': '归纳概括',
        'scoring_mode': 'point_based',
        'selected_reference_count': 2,
        'selected_references': [
            {'reference_id': 1, 'organization': '甲'},
            {'reference_id': 2, 'organization': '乙'},
        ],
        'points': [],
        'dimensions': [{'dimension': 'content', 'label': '内容', 'weight': 100}],
    }
    result = validate_grading_result(
        {
            'point_matches': [],
            'dimension_scores': [{'dimension': 'content', 'score': 50}],
            'reference_fusion': '本题未提供参考答案。',
        },
        rubric=rubric,
        answer_text='作答',
    )
    assert '已纳入 2 份机构参考答案' in result['reference_fusion']
    assert '未提供参考答案' not in result['reference_fusion']
