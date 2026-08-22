from __future__ import annotations

import re

from typing import Any

from backend.plugin.agent.service.shenlun.common import (
    RUBRIC_VERSION,
    clean,
    content_weight,
    default_dimensions,
    stable_hash,
)

VALID_TIERS = {'core', 'material_core', 'supporting', 'disputed'}
VALID_IMPORTANCE = {'critical', 'major', 'supporting'}


def normalize_references(context: dict[str, Any]) -> list[dict[str, Any]]:
    """把题库 V2 的异构解析数据转换成可追踪参考答案。"""
    candidates: list[tuple[str, Any]] = []
    answer_data = context.get('answer_data')
    grading_config = context.get('grading_config')
    if answer_data:
        candidates.append(('标准答案', answer_data))
    if grading_config:
        candidates.append(('评分配置', grading_config))
    for index, explanation in enumerate(context.get('explanations') or [], start=1):
        candidates.append((f'题库解析{index}', explanation))

    references: list[dict[str, Any]] = []
    seen: set[str] = set()
    for organization, value in candidates:
        answer_text, scoring_points, notes = _reference_fields(value)
        source_hash = stable_hash((answer_text, scoring_points, notes))
        if not any((answer_text, scoring_points, notes)) or source_hash in seen:
            continue
        seen.add(source_hash)
        references.append({
            'id': len(references) + 1,
            'organization': organization,
            'answer_text': answer_text,
            'scoring_points': scoring_points,
            'notes': notes,
        })
    return references


def _reference_fields(value: Any) -> tuple[str, str, str]:
    if isinstance(value, str):
        return clean(value, 5000), '', ''
    if isinstance(value, list):
        return '', clean(value, 5000), ''
    if not isinstance(value, dict):
        return clean(value, 5000), '', ''
    answer_keys = ('answer_text', 'reference_answer', 'standard_answer', 'answer')
    point_keys = ('scoring_points', 'points', 'rubric', 'keywords', 'key_points')
    note_keys = ('notes', 'analysis', 'explanation', 'requirements')
    return (
        _first_value(value, answer_keys),
        _first_value(value, point_keys),
        _first_value(value, note_keys),
    )


def _first_value(value: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        if value.get(key):
            return clean(value[key], 5000)
    return ''


def validate_rubric(  # noqa: C901
    raw: dict[str, Any],
    *,
    question_id: int,
    question_type: str,
    max_score: float,
    word_limit: str,
    materials: list[dict[str, Any]],
    references: list[dict[str, Any]],
) -> dict[str, Any]:
    """校验模型评分基准，系统负责证据、权重和稳定键。"""
    if not isinstance(raw, dict) or not isinstance(raw.get('points'), list):
        raise TypeError('评分基准缺少 points 数组')
    references_by_id = {int(item['id']): item for item in references}
    organization_count = len(references)
    core_threshold = max(2, (organization_count + 1) // 2)
    points: list[dict[str, Any]] = []

    for candidate in raw['points'][:30]:
        if not isinstance(candidate, dict):
            continue
        expression = clean(candidate.get('canonical_expression') or candidate.get('label'), 180)
        label = clean(candidate.get('label') or expression, 60)
        if not expression or not label:
            continue
        evidence = _verified_material_evidence(candidate, materials, expression)
        reference_ids = _reference_ids(candidate, references_by_id)
        tier = candidate.get('tier') if candidate.get('tier') in VALID_TIERS else 'supporting'
        if materials and not evidence:
            tier = 'disputed'
        if not evidence and not reference_ids:
            tier = 'disputed'
        organizations = {str(references_by_id[item].get('organization') or item) for item in reference_ids}
        if tier == 'core' and organization_count > 1 and len(organizations) < core_threshold:
            tier = 'supporting'
        if tier == 'material_core' and organization_count > 1 and len(organizations) >= core_threshold:
            tier = 'core'

        importance = candidate.get('importance')
        if importance not in VALID_IMPORTANCE:
            importance = 'critical' if tier in {'core', 'material_core'} else 'supporting'
        required = tier in {'core', 'material_core'} and candidate.get('required_for_full_score') is not False
        coverage_role = 'required' if required else 'bonus'
        alternative_group = clean(candidate.get('alternative_group'), 80)
        if question_type == '综合写作' and tier in {'core', 'material_core', 'supporting'}:
            coverage_role = 'alternative'
            required = False
            alternative_group = alternative_group or 'essay-evidence'
        suggested_weight = _positive_number(candidate.get('suggested_weight') or candidate.get('weight'))
        if tier == 'disputed' or coverage_role == 'bonus':
            suggested_weight = 0.0
        elif not suggested_weight:
            suggested_weight = {'critical': 4.0, 'major': 2.0, 'supporting': 1.0}[importance]

        point = {
            'label': label,
            'canonical_expression': expression,
            'aliases': [clean(item, 80) for item in candidate.get('aliases') or [] if clean(item)][:8],
            'tier': tier,
            'importance': importance,
            'suggested_weight': suggested_weight,
            'weight_reason': clean(candidate.get('weight_reason'), 220)
            or '依据题目任务、材料支撑和答案完整性确定相对权重。',
            'coverage_role': coverage_role,
            'alternative_group': alternative_group,
            'required_for_full_score': required,
            'required_elements': [clean(item, 80) for item in candidate.get('required_elements') or [] if clean(item)][
                :6
            ],
            'optional_details': [clean(item, 100) for item in candidate.get('optional_details') or [] if clean(item)][
                :6
            ],
            'minimum_expression': clean(candidate.get('minimum_expression') or expression, 120),
            'material_evidence': evidence[:3],
            'reference_ids': reference_ids,
            'support_org_count': len(organizations),
            'confidence': _bounded(candidate.get('confidence'), 0.5),
        }
        supplied_key = clean(candidate.get('point_key'), 80)
        point['point_key'] = supplied_key if re.fullmatch(r'[A-Za-z0-9_.:-]+', supplied_key) else _stable_key(point)
        points.append(point)

    _normalize_essay_roles(points, question_type)
    scoreable = [
        point
        for point in points
        if point['suggested_weight'] > 0 and point['coverage_role'] in {'required', 'alternative'}
    ]
    if not scoreable:
        raise ValueError('评分基准没有通过材料校验的有效采分点')
    equal_weights = len({round(point['suggested_weight'], 4) for point in scoreable}) == 1
    if len(scoreable) >= 3 and equal_weights and not clean(raw.get('equal_weight_reason'), 240):
        raise ValueError('三个及以上采分点等权，但未说明等权理由')

    display_max_score = max_score
    target_content_score = content_weight(question_type, 100)
    base_total = sum(point['suggested_weight'] for point in scoreable)
    for point in points:
        point['weight'] = (
            round(target_content_score * point['suggested_weight'] / base_total, 3)
            if point['suggested_weight']
            else 0.0
        )
    difference = round(target_content_score - sum(point['weight'] for point in points), 3)
    if difference:
        scoreable[-1]['weight'] = round(scoreable[-1]['weight'] + difference, 3)

    return {
        'schema_version': RUBRIC_VERSION,
        'question_id': question_id,
        'max_score': 100.0,
        'display_max_score': display_max_score,
        'score_is_estimated': False,
        'question_type': question_type,
        'word_limit': word_limit,
        'scoring_mode': 'holistic_essay' if question_type == '综合写作' else 'point_based',
        'selected_reference_count': len(references),
        'selected_references': [
            {'reference_id': item['id'], 'organization': item['organization']} for item in references
        ],
        'task_constraints': raw.get('task_constraints') if isinstance(raw.get('task_constraints'), dict) else {},
        'points': points,
        'equal_weight_reason': clean(raw.get('equal_weight_reason'), 240),
        'dimensions': default_dimensions(question_type, 100),
        'conflicts': [clean(item, 240) for item in raw.get('conflicts') or [] if clean(item)][:8],
    }


def _verified_material_evidence(
    candidate: dict[str, Any], materials: list[dict[str, Any]], expression: str
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for item in candidate.get('material_evidence') or []:
        if not isinstance(item, dict):
            continue
        quote = clean(item.get('quote'), 160)
        material = _find_material(quote, materials)
        if material:
            evidence.append({'material_number': material.get('material_number'), 'quote': quote})
    if evidence:
        return evidence
    material = _find_material(expression, materials)
    if material:
        return [{'material_number': material.get('material_number'), 'quote': expression}]
    return []


def _find_material(quote: str, materials: list[dict[str, Any]]) -> dict[str, Any] | None:
    compact_quote = re.sub(r'[^\w\u4e00-\u9fff]', '', quote)
    if len(compact_quote) < 4:
        return None
    for material in materials:
        compact_content = re.sub(r'[^\w\u4e00-\u9fff]', '', str(material.get('content') or ''))
        if compact_quote in compact_content:
            return material
    return None


def _reference_ids(candidate: dict[str, Any], references: dict[int, dict[str, Any]]) -> list[int]:
    explicit = sorted({
        int(value)
        for value in candidate.get('reference_ids') or []
        if str(value).isdigit() and int(value) in references
    })
    if explicit:
        return explicit
    cues = ' '.join(
        clean(value)
        for value in (
            candidate.get('label'),
            candidate.get('canonical_expression'),
            *(candidate.get('aliases') or []),
        )
        if clean(value)
    )
    cue_chars = set(re.sub(r'[^\w\u4e00-\u9fff]', '', cues))
    if len(cue_chars) < 4:
        return []
    result: list[int] = []
    for reference_id, reference in references.items():
        text = ' '.join(str(reference.get(key) or '') for key in ('answer_text', 'scoring_points', 'notes'))
        reference_chars = set(re.sub(r'[^\w\u4e00-\u9fff]', '', text))
        if reference_chars and len(cue_chars & reference_chars) / len(cue_chars) >= 0.55:
            result.append(reference_id)
    return result


def _normalize_essay_roles(points: list[dict[str, Any]], question_type: str) -> None:
    if question_type != '综合写作':
        return
    scoreable = [point for point in points if point['suggested_weight'] > 0 and point['tier'] != 'disputed']
    thesis = next(
        (point for point in scoreable if re.search(r'中心立意|中心论点|总论点|核心观点|文章主旨|主题', point['label'])),
        scoreable[0] if scoreable else None,
    )
    for point in scoreable:
        if point is thesis:
            point['coverage_role'] = 'required'
            point['required_for_full_score'] = True
            point['alternative_group'] = ''
        else:
            point['coverage_role'] = 'alternative'
            point['required_for_full_score'] = False
            point['alternative_group'] = point['alternative_group'] or 'essay-evidence'


def _stable_key(point: dict[str, Any]) -> str:
    payload = {
        'expression': point['canonical_expression'],
        'quotes': sorted(item['quote'] for item in point['material_evidence']),
    }
    return f'point-{stable_hash(payload)[:16]}'


def _positive_number(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return number if number > 0 else 0.0


def _bounded(value: Any, default: float) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default
