from __future__ import annotations

import re

from typing import Any

from backend.plugin.agent.service.shenlun.calibration import apply_score_calibration
from backend.plugin.agent.service.shenlun.common import RESULT_VERSION, clean, coverage_factor
from backend.plugin.agent.service.shenlun.evidence_resolution import resolve_answer_evidence


def validate_grading_result(  # noqa: C901
    raw: dict[str, Any],
    *,
    rubric: dict[str, Any],
    answer_text: str,
    evidence: list[dict[str, Any]] | None = None,
    calibration_policy: dict[str, Any] | None = None,
    reviewed: bool = False,
) -> dict[str, Any]:
    """验证批改结果并由系统重算点式题内容分。"""
    if isinstance(raw, dict) and isinstance(raw.get('evaluation'), dict):
        raw = raw['evaluation']
    if not isinstance(raw, dict):
        raise TypeError('批改结果不是 JSON 对象')

    points = [point for point in rubric.get('points') or [] if point.get('point_key')]
    point_by_key = {point['point_key']: point for point in points}
    candidates = {
        str(item.get('point_key')): item
        for item in raw.get('point_matches') or []
        if isinstance(item, dict) and item.get('point_key')
    }
    matches: list[dict[str, Any]] = []
    for point in points:
        candidate = candidates.get(point['point_key']) or {}
        if not candidate and point.get('source_point_key'):
            candidate = candidates.get(point['source_point_key']) or {}
        status = candidate.get('status')
        if status not in {'hit', 'partial', 'miss'}:
            status = 'miss'
        quote = clean(candidate.get('answer_quote'), 240)
        resolution = (
            resolve_answer_evidence(quote, answer_text)
            if status in {'hit', 'partial'}
            else {'status': 'not_required', 'quote': '', 'spans': []}
        )
        if resolution['status'] == 'resolved':
            quote = clean(resolution.get('quote'), 240)
        matches.append({
            'point_key': point['point_key'],
            'status': status,
            'coverage_ratio': coverage_factor(candidate.get('coverage_ratio'), status),
            'answer_quote': quote,
            'reason': _point_reason(status, candidate.get('reason'), point),
            'weight': round(float(point.get('weight') or 0), 3),
            'importance': point.get('importance') or 'supporting',
            'coverage_role': point.get('coverage_role') or 'bonus',
            'evidence_status': resolution['status'],
            'evidence_spans': resolution.get('spans') or [],
            'confidence': _bounded(candidate.get('confidence'), 0.7),
            'missing_elements': [clean(item, 100) for item in candidate.get('missing_elements') or [] if clean(item)][
                :6
            ],
        })

    scoring_mode = rubric.get('scoring_mode') or 'point_based'
    weighted_coverage = round(
        sum(
            match['weight'] * match['coverage_ratio']
            for match in matches
            if match['coverage_role'] in {'required', 'alternative'}
            and not (
                scoring_mode == 'point_based'
                and match['status'] in {'hit', 'partial'}
                and match['evidence_status'] == 'unresolved'
            )
        ),
        2,
    )
    dimensions = _validate_dimensions(raw.get('dimension_scores'), rubric, answer_text)
    content_score = next(
        (item['score'] for item in dimensions if item['dimension'] == 'content'),
        0.0,
    )
    if scoring_mode == 'point_based' and answer_text.strip():
        content_dimension = next(item for item in dimensions if item['dimension'] == 'content')
        content_score = min(content_dimension['max_score'], weighted_coverage)
        content_dimension['score'] = round(content_score, 2)
        content_dimension['reason'] = clean(
            content_dimension.get('reason') or '内容分由必答采分点覆盖及答案原文证据重算。',
            300,
        )

    annotations = _validate_annotations(raw.get('annotations'), answer_text, point_by_key)
    raw_score_percent = round(sum(item['score'] for item in dimensions), 2)
    review_reasons = [
        f'unresolved_required_evidence:{match["point_key"]}'
        for match in matches
        if match['coverage_role'] == 'required'
        and match['status'] in {'hit', 'partial'}
        and match['evidence_status'] == 'unresolved'
    ]
    if scoring_mode == 'holistic_essay':
        content_max = next(item['max_score'] for item in dimensions if item['dimension'] == 'content')
        if abs(content_score - weighted_coverage) > content_max * 0.35:
            review_reasons.append('essay_content_diagnostic_divergence')
        essay_diagnostic = ' '.join(item.get('reason') or '' for item in dimensions)
        if raw_score_percent >= 70 and re.search(
            r'(?:关键)?事实(?:偏差|错误)|材料误读|论证(?:空泛|薄弱|不足)|未能结合.{0,12}(?:材料|案例)|主要(?:部分|段落).{0,8}(?:缺少|不足)',
            essay_diagnostic,
        ):
            review_reasons.append('essay_high_band_diagnostic_conflict')

    display_max_score = float(rubric.get('display_max_score') or rubric.get('max_score') or 100)
    score, score_calibration = apply_score_calibration(raw_score_percent, calibration_policy)
    # 与 YanShen 保持一致:总分按 0.5 的倍数取整(round-half)
    display_score = round(score * display_max_score / 100 * 2) / 2
    _redistribute_dimension_scores(dimensions, score)
    content_score = next((item['score'] for item in dimensions if item['dimension'] == 'content'), 0.0)
    display_scale = display_max_score / 100
    for dimension in dimensions:
        dimension['display_max_score'] = round(dimension['max_score'] * display_scale, 2)
        dimension['display_score'] = round(dimension['score'] * display_scale, 2)
    personalized_findings = _validate_personalized_findings(raw.get('personalized_findings'), evidence or [])
    score_status = 'provisional' if review_reasons else 'valid'
    if reviewed and not review_reasons:
        score_status = 'valid'
    return {
        'schema_version': RESULT_VERSION,
        'score_status': score_status,
        'status': score_status,
        'question_type': rubric.get('question_type') or '',
        'word_limit': rubric.get('word_limit') or '',
        'score': score,
        'raw_score': raw_score_percent,
        'display_score': display_score,
        'max_score': 100.0,
        'display_max_score': display_max_score,
        'score_is_estimated': bool(rubric.get('score_is_estimated')),
        'answer_word_count': len(answer_text),
        'point_matches': matches,
        'dimension_scores': dimensions,
        'weighted_coverage_score': weighted_coverage,
        'display_weighted_coverage_score': round(weighted_coverage * display_scale, 2),
        'content_score': round(content_score, 2),
        'display_content_score': round(content_score * display_scale, 2),
        'score_calibration': score_calibration,
        'holistic_adjustment_reason': clean(raw.get('holistic_adjustment_reason'), 360),
        'annotations': annotations[:12],
        'reference_fusion': _validated_reference_fusion(raw.get('reference_fusion'), rubric),
        'material_reading': [clean(item, 360) for item in raw.get('material_reading') or [] if clean(item)][:12],
        'optimization_suggestions': [
            clean(item, 300) for item in raw.get('optimization_suggestions') or [] if clean(item)
        ][:10],
        'personalized_findings': personalized_findings,
        'overall_summary': clean(raw.get('overall_summary'), 360),
        'summary': raw.get('summary') if isinstance(raw.get('summary'), dict) else {},
        'revised_answer': str(raw.get('revised_answer') or '').strip(),
        'review': {
            'triggered': bool(review_reasons),
            'reasons': review_reasons,
            'decision': 'confirmed'
            if reviewed and not review_reasons
            else ('required' if review_reasons else 'not_needed'),
        },
        'validation_errors': review_reasons,
        'quality_check': {'passed': not review_reasons, 'notes': review_reasons},
    }


def _validate_personalized_findings(
    raw: Any,
    evidence: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    valid_ids = {str(item.get('evidence_id')) for item in evidence if item.get('role') == 'personalization'}
    stable = len({item.get('attempt_id') for item in evidence if item.get('attempt_id')}) >= 2
    result: list[dict[str, Any]] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        evidence_ids = [str(value) for value in item.get('evidence_ids') or [] if str(value) in valid_ids]
        finding = clean(item.get('finding'), 220)
        if not finding or not evidence_ids:
            continue
        result.append({
            'finding': finding,
            'root_cause': clean(item.get('root_cause'), 220),
            'next_step': clean(item.get('next_step'), 220),
            'evidence_ids': evidence_ids[:6],
            'confidence': 'recurring' if item.get('confidence') == 'recurring' and stable else 'stage',
        })
    return result[:6]


def _redistribute_dimension_scores(dimensions: list[dict[str, Any]], target_score: float) -> None:
    current_score = sum(float(item.get('score') or 0) for item in dimensions)
    difference = round(target_score - current_score, 2)
    if not difference:
        return
    if difference < 0:
        denominator = current_score or 1.0
        for item in dimensions:
            share = difference * float(item.get('score') or 0) / denominator
            item['score'] = round(max(0.0, float(item.get('score') or 0) + share), 2)
    else:
        headroom = sum(float(item.get('max_score') or 0) - float(item.get('score') or 0) for item in dimensions) or 1.0
        for item in dimensions:
            available = float(item.get('max_score') or 0) - float(item.get('score') or 0)
            item['score'] = round(
                min(
                    float(item.get('max_score') or 0), float(item.get('score') or 0) + difference * available / headroom
                ),
                2,
            )
    residual = round(target_score - sum(float(item.get('score') or 0) for item in dimensions), 2)
    if residual:
        for item in dimensions:
            candidate = round(float(item.get('score') or 0) + residual, 2)
            if 0 <= candidate <= float(item.get('max_score') or 0):
                item['score'] = candidate
                break


def _validate_dimensions(raw: Any, rubric: dict[str, Any], answer_text: str) -> list[dict[str, Any]]:
    definitions = rubric.get('dimensions') or []
    expected_total = float(rubric.get('max_score') or 100)
    if abs(sum(float(item.get('weight') or 0) for item in definitions) - expected_total) > 0.01:
        raise ValueError('评分维度满分未闭合到题目满分')
    candidates = {
        str(item.get('dimension')): item for item in raw or [] if isinstance(item, dict) and item.get('dimension')
    }
    result: list[dict[str, Any]] = []
    for definition in definitions:
        dimension = str(definition['dimension'])
        candidate = candidates.get(dimension)
        if candidate is None and answer_text.strip():
            raise ValueError(f'批改结果缺少 {dimension} 维度得分')
        try:
            score = 0.0 if not answer_text.strip() else float(candidate.get('score'))
        except (AttributeError, TypeError, ValueError):
            raise ValueError(f'{dimension} 维度得分不是有效数字') from None
        max_score = float(definition.get('weight') or 0)
        if score < 0 or score > max_score:
            raise ValueError(f'{dimension} 维度得分超出有效范围')
        result.append({
            'dimension': dimension,
            'label': definition.get('label') or dimension,
            'max_score': max_score,
            'score': round(score, 2),
            'reason': '空白答案。' if not answer_text.strip() else clean(candidate.get('reason'), 300),
        })
    return result


def _validate_annotations(raw: Any, answer_text: str, point_by_key: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    severities = {'positive', 'low', 'medium', 'high', 'critical'}
    default_severity = {
        'good': 'positive',
        'polish': 'low',
        'change': 'medium',
        'delete': 'high',
        'add': 'high',
        'critical': 'critical',
    }
    result: list[dict[str, Any]] = []
    for item in raw or []:
        if not isinstance(item, dict):
            continue
        kind = item.get('kind') if item.get('kind') in default_severity else 'change'
        quote = clean(item.get('quote'), 180)
        anchor = clean(item.get('anchor'), 180)
        if kind != 'add' and (not quote or quote not in answer_text):
            continue
        if kind == 'add' and (not anchor or anchor not in answer_text):
            continue
        severity = item.get('severity')
        result.append({
            'kind': kind,
            'quote': quote,
            'replacement': clean(item.get('replacement'), 200),
            'reason': clean(item.get('reason'), 240),
            'point_key': item.get('point_key') if item.get('point_key') in point_by_key else '',
            'severity': severity if severity in severities else default_severity[kind],
            'anchor': anchor,
        })
    return result


def _point_reason(status: str, value: Any, point: dict[str, Any]) -> str:
    reason = clean(value, 300)
    label = clean(point.get('label'), 80) or '该采分点'
    if status == 'miss' and any(
        claim in reason
        for claim in (
            '完整覆盖', '充分覆盖', '完全覆盖', '已经覆盖', '已覆盖', '明确体现',
            '准确体现', '完整体现', '已命中', '完全命中',
        )
    ):
        return f'原答案未提供能够证明“{label}”的明确表述；判断仅依据本次作答原文。'
    if reason:
        return reason
    if status == 'miss':
        return f'原答案未出现“{label}”对应的明确表述。'
    if status == 'partial':
        return f'原答案仅覆盖“{label}”的部分核心语义。'
    return f'原答案已明确覆盖“{label}”。'


def _reference_fusion(rubric: dict[str, Any]) -> str:
    references = rubric.get('selected_references') or []
    if not references:
        return '本题未提供独立参考答案，评分仅依据题干任务与材料原文。'
    organizations = '、'.join(item['organization'] for item in references)
    return f'本题已纳入 {len(references)} 份参考上下文（{organizations}），并以题干和材料作为最高事实来源。'


def _validated_reference_fusion(value: Any, rubric: dict[str, Any]) -> str:
    text = clean(value, 600)
    references = rubric.get('selected_references') or []
    count = int(rubric.get('selected_reference_count') or len(references))
    if count <= 0:
        return text or _reference_fusion(rubric)
    organizations = '、'.join(
        str(item.get('organization') or '').strip()
        for item in references
        if item.get('organization')
    )
    if count == 1:
        source = f'（{organizations}）' if organizations else ''
        return (
            f'本题仅有 1 份机构参考答案{source}，用于辅助核对采分点；'
            '评分同时依据题干任务与材料原文，不把单份答案视为唯一标准。'
        )
    prefix = f'本题已纳入 {count} 份机构参考答案'
    if organizations:
        prefix += f'（{organizations}）'
    prefix += '进行融合。'
    no_reference_claims = ('无参考答案', '没有参考答案', '未提供参考答案', '无额外参考答案')
    if any(claim in text for claim in no_reference_claims):
        text = '系统已结合机构答案全文与本题材料核验共性核心点和差异补充点。'
    if text.startswith(('本题已纳入', '本题纳入')):
        _, separator, remainder = text.partition('。')
        text = remainder.strip() if separator else ''
    return prefix + (text or '系统已结合机构答案全文与本题材料核验采分点。')


def _bounded(value: Any, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default
