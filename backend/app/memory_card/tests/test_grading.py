#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import pytest

from backend.app.memory_card.service.grading_service import (
    build_study_content,
    content_hash,
    derive_available_modes,
    grade_answer,
    issue_correction_ticket,
    render_material,
    resolve_correction_ticket,
    validate_content,
)
from backend.common.exception import errors


def material() -> dict:
    return {
        'segments': [
            {'type': 'text', 'text': '我是一个'},
            {'type': 'point', 'id': 'p1', 'correct': '好', 'wrong': '坏'},
            {'type': 'text', 'text': '人，应该保持'},
            {'type': 'point', 'id': 'p2', 'correct': '善良', 'wrong': '恶意'},
            {'type': 'text', 'text': '。'},
        ],
    }


def points() -> list[dict]:
    return [item for item in material()['segments'] if item['type'] == 'point']


def test_validate_and_render_multi_point_material() -> None:
    content = material()
    validate_content(content=content)
    assert derive_available_modes(content) == ['input', 'reveal', 'choice', 'correction']
    assert render_material(content) == '我是一个好人，应该保持善良。'
    assert render_material(content, wrong=True) == '我是一个坏人，应该保持恶意。'


def test_validate_rejects_missing_or_duplicate_points() -> None:
    try:
        validate_content(content={'segments': [{'type': 'text', 'text': '没有记忆点'}]})
        raise AssertionError('should raise')
    except errors.RequestError:
        pass

    bad = {
        'segments': [
            {'type': 'text', 'text': 'a'},
            {'type': 'point', 'id': 'p1', 'correct': '好', 'wrong': '坏'},
            {'type': 'point', 'id': 'p1', 'correct': '善', 'wrong': '恶'},
        ],
    }
    try:
        validate_content(content=bad)
        raise AssertionError('should raise')
    except errors.RequestError:
        pass


def test_grade_input_and_choice_with_multiple_points() -> None:
    result, details = grade_answer(
        mode='input',
        response={'p1': '好', 'p2': '善良'},
        points=points(),
    )
    assert result == 'correct'
    assert all(item['correct'] for item in details)

    result, details = grade_answer(
        mode='choice',
        response={'p1': '好', 'p2': '恶意'},
        points=points(),
    )
    assert result == 'wrong'
    assert details[0]['correct'] is True
    assert details[1]['correct'] is False


def test_grade_reveal_is_undetermined() -> None:
    result, details = grade_answer(mode='input', response=None, points=points())
    assert result == 'undetermined'
    assert all(item['correct'] is False for item in details)


def test_grade_correction_correct_and_wrong_cases() -> None:
    result, _ = grade_answer(
        mode='correction',
        response={'case': 'correct', 'action': 'full_correct', 'point_ids': []},
        points=points(),
    )
    assert result == 'correct'

    result, _ = grade_answer(
        mode='correction',
        response={'case': 'wrong', 'action': 'select_error', 'point_ids': ['p2']},
        points=points(),
    )
    assert result == 'correct'

    result, _ = grade_answer(
        mode='correction',
        response={'case': 'wrong', 'action': 'full_correct', 'point_ids': []},
        points=points(),
    )
    assert result == 'wrong'


def test_build_study_content_keeps_multiple_points_safe() -> None:
    choice = build_study_content(content=material(), mode='choice')
    assert choice['mode'] == 'choice'
    assert [item['id'] for item in choice['segments'] if item['type'] == 'point'] == ['p1', 'p2']
    assert choice['segments'][1]['options'] == ['好', '坏']
    assert 'correct' not in choice['segments'][1]
    assert 'wrong' not in choice['segments'][1]

    correction = build_study_content(content=material(), mode='correction')
    assert correction['correction_case'] in ('correct', 'wrong')
    assert correction['segments'][1]['text'] in ('好', '坏')


@pytest.mark.parametrize(
    ('selected', 'action', 'wrong_ids', 'expected'),
    [
        (['p2', 'p1'], 'select_error', {'p1', 'p2'}, 'correct'),
        (['p1'], 'select_error', {'p1', 'p2'}, 'wrong'),
        (['p1', 'p2', 'p3'], 'select_error', {'p1', 'p2'}, 'wrong'),
        (['p3'], 'select_error', {'p1', 'p2'}, 'wrong'),
        ([], 'full_correct', {'p1', 'p2'}, 'wrong'),
        ([], 'full_correct', set(), 'correct'),
        (['p1'], 'select_error', set(), 'wrong'),
    ],
)
def test_grade_multiple_correction(selected: list[str], action: str, wrong_ids: set[str], expected: str) -> None:
    candidates = [*points(), {'id': 'p3', 'correct': '正常', 'wrong': '异常'}]
    result, details = grade_answer(
        mode='correction',
        response={'action': action, 'point_ids': selected, 'case': 'correct'},
        points=candidates,
        correction_error_ids=wrong_ids,
    )
    assert result == expected
    assert [item['correct'] for item in details] == [
        (item['id'] in selected) == (item['id'] in wrong_ids) for item in candidates
    ]


def test_correction_ticket_rebuilds_original_variant_and_is_bound_to_user_and_revision() -> None:
    candidates = points()
    ticket, errors_in_sentence = issue_correction_ticket(7, 10, candidates)
    content = build_study_content(content=material(), mode='correction', correction_error_ids=errors_in_sentence)
    assert content['correction_case'] is None
    assert resolve_correction_ticket(ticket, 7, 10, candidates) == errors_in_sentence
    shown_points = [segment for segment in content['segments'] if segment['type'] == 'point']
    for segment, point in zip(shown_points, candidates, strict=True):
        assert segment['text'] == point['wrong' if point['id'] in errors_in_sentence else 'correct']

    for user_id, revision_id in [(8, 10), (7, 11)]:
        with pytest.raises(errors.RequestError):
            resolve_correction_ticket(ticket, user_id, revision_id, candidates)
    with pytest.raises(errors.RequestError):
        resolve_correction_ticket(f'{ticket[:-1]}z', 7, 10, candidates)


def test_multiple_correction_can_show_correct_and_wrong_points_together() -> None:
    content = build_study_content(content=material(), mode='correction', correction_error_ids={'p2'})
    assert [(point['id'], point['text']) for point in content['segments'] if point['type'] == 'point'] == [
        ('p1', '好'),
        ('p2', '恶意'),
    ]


def test_content_hash_is_deterministic() -> None:
    content = material()
    assert content_hash(content) == content_hash(content)
    assert content_hash(content) != content_hash({**content, 'segments': [{'type': 'text', 'text': 'changed'}]})
