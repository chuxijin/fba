#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""记忆卡素材校验、四种玩法判分与学习内容构造。"""

import hashlib
import json
import secrets

from typing import Any

from backend.common.exception import errors

PLAY_MODES = ('input', 'reveal', 'choice', 'correction')


def normalize_text(value: Any) -> str:
    """规范化文本用于宽松比对：去空白、统一大小写。"""
    return str(value or '').strip().casefold()


def normalize_answer_list(values: list[str]) -> list[str]:
    return [normalize_text(item) for item in values if normalize_text(item)]


def is_acceptable(value: Any, answers: list[str]) -> bool:
    normalized = normalize_text(value)
    return bool(normalized and normalized in normalize_answer_list(answers))


def extract_points(content: dict[str, Any]) -> list[dict[str, Any]]:
    """从统一素材结构中提取记忆点。"""
    return [segment for segment in content.get('segments') or [] if segment.get('type') == 'point']


def render_material(content: dict[str, Any], *, wrong: bool = False) -> str:
    """渲染完整正确句或完整错误句。"""
    result: list[str] = []
    for segment in content.get('segments') or []:
        if segment.get('type') == 'point':
            result.append(str(segment.get('wrong' if wrong else 'correct') or ''))
        else:
            result.append(str(segment.get('text') or ''))
    return ''.join(result)


def derive_available_modes(content: dict[str, Any]) -> list[str]:
    """根据素材是否包含正确/错误内容推导可用玩法。"""
    points = extract_points(content)
    if not points:
        return []
    modes = ['input', 'reveal']
    if all(point.get('options') or [point.get('correct'), point.get('wrong')] for point in points):
        modes.append('choice')
    if all(str(point.get('wrong') or '').strip() for point in points):
        modes.append('correction')
    return modes


def validate_content(  # noqa: C901
    *,
    content: dict[str, Any],
    card_type: str | None = None,
    response_mode: str | None = None,
) -> None:
    """校验统一素材结构；旧玩法参数仅为兼容调用保留。"""
    segments = content.get('segments') or []
    if not segments:
        raise errors.RequestError(msg='素材不能为空')
    points = extract_points(content)
    if not points:
        raise errors.RequestError(msg='至少需要一个记忆点')

    point_ids: set[str] = set()
    for segment in segments:
        segment_type = segment.get('type')
        if segment_type == 'text':
            if not str(segment.get('text') or '').strip():
                raise errors.RequestError(msg='普通文本片段不能为空')
            continue
        if segment_type != 'point':
            raise errors.RequestError(msg='素材片段类型不支持')
        point_id = str(segment.get('id') or '')
        correct = str(segment.get('correct') or '').strip()
        wrong = str(segment.get('wrong') or '').strip()
        if not point_id or not point_id.startswith('p'):
            raise errors.RequestError(msg='记忆点标识必须以 p 开头，如 p1')
        if point_id in point_ids:
            raise errors.RequestError(msg=f'记忆点标识 {point_id} 重复')
        point_ids.add(point_id)
        if not correct:
            raise errors.RequestError(msg=f'记忆点 {point_id} 缺少正确内容')
        if not wrong:
            raise errors.RequestError(msg=f'记忆点 {point_id} 缺少错误内容')
        if normalize_text(correct) == normalize_text(wrong):
            raise errors.RequestError(msg=f'记忆点 {point_id} 的正确内容和错误内容不能相同')
        options = [str(item).strip() for item in (segment.get('options') or []) if str(item).strip()]
        if options and not any(normalize_text(item) == normalize_text(correct) for item in options):
            raise errors.RequestError(msg=f'记忆点 {point_id} 的选择项必须包含正确内容')
        if options and not any(normalize_text(item) == normalize_text(wrong) for item in options):
            raise errors.RequestError(msg=f'记忆点 {point_id} 的选择项必须包含错误内容')


def build_study_content(*, content: dict[str, Any], mode: str) -> dict[str, Any]:
    """构造指定玩法的安全学习内容，不返回正确答案。"""
    if mode not in PLAY_MODES:
        raise errors.RequestError(msg=f'不支持的学习玩法：{mode}')
    available_modes = derive_available_modes(content)
    if mode not in available_modes:
        raise errors.RequestError(msg=f'当前素材不支持学习玩法：{mode}')

    correction_case: str | None = None
    if mode == 'correction':
        correction_case = secrets.choice(('correct', 'wrong'))

    segments: list[dict[str, Any]] = []
    for segment in content.get('segments') or []:
        if segment.get('type') == 'text':
            segments.append({'type': 'text', 'text': segment.get('text', '')})
            continue
        item: dict[str, Any] = {
            'type': 'point',
            'id': segment['id'],
        }
        if mode == 'correction':
            item['text'] = segment['wrong'] if correction_case == 'wrong' else segment['correct']
        if mode == 'choice':
            options = segment.get('options') or [segment['correct'], segment['wrong']]
            item['options'] = list(dict.fromkeys(options))
        segments.append(item)

    return {
        'mode': mode,
        'segments': segments,
        'correction_case': correction_case,
    }


def grade_cloze(response: Any, points: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """判定输入填空或选择填空。"""
    if not isinstance(response, dict):
        response = {}
    results: list[dict[str, Any]] = []
    all_correct = True
    for point in points:
        point_id = str(point.get('id') or '')
        user_answer = response.get(point_id)
        correct = is_acceptable(user_answer, [str(point.get('correct') or '')])
        all_correct = all_correct and correct
        results.append(
            {
                'blank_id': point_id,
                'user_answer': user_answer,
                'correct': correct,
                'correct_answer': point.get('correct'),
            }
        )
    if not response:
        return 'undetermined', results
    return ('correct' if all_correct else 'wrong'), results


def grade_correction(response: Any, points: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """判定纠错：错误句点击错误点，正确句点击完整正确。"""
    if not isinstance(response, dict):
        return 'undetermined', []
    case = response.get('case')
    action = response.get('action')
    selected = {str(item) for item in (response.get('point_ids') or [])}
    valid_ids = {str(point.get('id')) for point in points}

    if case == 'correct':
        correct = action == 'full_correct' and not selected
    elif case == 'wrong':
        correct = action == 'select_error' and bool(selected & valid_ids)
    else:
        correct = False

    details = [
        {
            'blank_id': str(point.get('id')),
            'user_answer': action,
            'correct': correct,
            'correct_answer': point.get('correct'),
        }
        for point in points
    ]
    if not action:
        return 'undetermined', details
    return ('correct' if correct else 'wrong'), details


def grade_answer(*, mode: str, response: Any, points: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """按本次学习玩法分派判分。"""
    if mode == 'correction':
        return grade_correction(response, points)
    return grade_cloze(response, points)


def content_hash(content: dict[str, Any]) -> str:
    """计算卡片内容规范化哈希。"""
    raw = json.dumps(content, ensure_ascii=True, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(raw.encode()).hexdigest()


def recommend_rating(*, check_result: str, revealed: bool) -> int:
    """由客观判定推导推荐自评分（1-4）。"""
    if check_result == 'correct':
        return 3 if not revealed else 2
    if check_result == 'wrong':
        return 1
    return 2
