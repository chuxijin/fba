"""考研政治客观卷：固定卷型、双题型抽题、幂等快照与前端口径回归。"""

import asyncio

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from pydantic import ValidationError

from backend.app.question_bank_v2.crud.crud_practice import PracticeCandidate
from backend.app.question_bank_v2.schema.practice import CreatePracticeSessionParam, PracticeModuleQuota
from backend.app.question_bank_v2.service import practice_service as module
from backend.app.question_bank_v2.service.practice_service import PracticeService
from backend.app.question_bank_v2.utils.politics_paper import PoliticsModuleQuota
from backend.common.exception import errors

#: 既有用例沿用「所选范围就是一个模块」的口径：单模块分满 16/17
SELECTED_SCOPE_MODULE = SimpleNamespace(code='kaoyan_politics_selected_scope', name='所选范围')


async def fake_single_scope_plan(
    db: Any = None,
    obj: Any = None,
    point_ids: Any = None,
) -> list[PoliticsModuleQuota]:
    await asyncio.sleep(0)
    if not point_ids:
        raise errors.RequestError(msg='所选抽题范围不可用，请返回重新选择')
    return [
        PoliticsModuleQuota(
            module=SELECTED_SCOPE_MODULE,
            point_ids=frozenset(point_ids),
            single_count=16,
            multiple_count=17,
        )
    ]


def politics_obj(mode: str = 'practice', **overrides: Any) -> CreatePracticeSessionParam:
    params: dict[str, Any] = {
        'source_type': 'custom',
        'knowledge_point_ids': [201, 202],
        'knowledge_system_id': 11,
        'paper_profile': 'kaoyan_politics',
        'mode': mode,
    }
    params.update(overrides)
    return CreatePracticeSessionParam(**params)


def candidate(question_id: int, score: str = '3') -> PracticeCandidate:
    return PracticeCandidate(
        question_id=question_id,
        bank_item_id=None,
        max_score=Decimal(score),
        display_config={'seed': question_id},
    )


def single_rows(count: int = 16) -> list[PracticeCandidate]:
    return [candidate(index) for index in range(1, count + 1)]


def multiple_rows(count: int = 17) -> list[PracticeCandidate]:
    return [candidate(index) for index in range(101, 101 + count)]


def test_paper_profile_normalizes_practice_to_33_items_without_timer() -> None:
    obj = politics_obj()

    assert obj.paper_profile == 'kaoyan_politics'
    assert obj.limit == 33
    assert obj.duration_minutes is None
    assert obj.mode == 'practice'
    assert obj.knowledge_point_ids == [201, 202]


def test_paper_profile_normalizes_exam_to_45_minutes() -> None:
    assert politics_obj('exam').duration_minutes == 45
    assert politics_obj('exam', limit=33, duration_minutes=45).duration_minutes == 45


def test_paper_profile_forces_shuffle_on() -> None:
    assert politics_obj(shuffle=False).shuffle is True
    assert politics_obj('exam', shuffle=False).shuffle is True


@pytest.mark.parametrize(
    'overrides',
    [
        {'source_type': 'bank', 'bank_id': 1},
        {'bank_id': 1},
        {'section_id': 2, 'bank_id': 1},
        {'question_ids': [1]},
        {'knowledge_point_ids': []},
        {'selection_strategy': 'high_error'},
        {'question_types': ['single_choice']},
        {'mode': 'mock'},
        {'include_knowledge_descendants': False},
        {
            'knowledge_point_ids': [201],
            'module_quotas': [PracticeModuleQuota(knowledge_point_id=201, count=33)],
            'limit': 33,
        },
    ],
)
def test_paper_profile_only_allows_plain_custom_knowledge_scope(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError, match='考研政治组卷仅支持按知识点范围'):
        politics_obj(**overrides)


@pytest.mark.parametrize('limit', [1, 16, 32, 34, 500])
def test_paper_profile_rejects_any_other_item_count(limit: int) -> None:
    with pytest.raises(ValidationError, match='考研政治组卷固定33题'):
        politics_obj(limit=limit)


@pytest.mark.parametrize(('mode', 'duration'), [('practice', 45), ('practice', 10), ('exam', 44), ('exam', 60)])
def test_paper_profile_rejects_non_matching_timer(mode: str, duration: int) -> None:
    with pytest.raises(ValidationError, match='考试限时45分钟，普通练习不限时'):
        politics_obj(mode, duration_minutes=duration)


def run_candidates(
    monkeypatch: pytest.MonkeyPatch,
    rows: Any,
    *,
    obj: CreatePracticeSessionParam | None = None,
    point_ids: set[int] | None = None,
) -> tuple[list[PracticeCandidate], list[dict[str, Any]]]:
    calls: list[dict[str, Any]] = []

    def get_candidates(_db: Any, **kwargs: Any) -> list[PracticeCandidate]:
        calls.append(kwargs)
        return rows(kwargs) if callable(rows) else rows

    monkeypatch.setattr(module.practice_session_item_dao, 'get_user_candidates', AsyncMock(side_effect=get_candidates))
    monkeypatch.setattr(PracticeService, '_politics_plan', fake_single_scope_plan, raising=False)
    result = asyncio.run(
        PracticeService._politics_candidates(
            db=None,
            user_id=7,
            obj=obj or politics_obj(),
            point_ids={201, 202} if point_ids is None else point_ids,
        )
    )
    return result, calls


def test_politics_candidates_draw_16_single_then_17_multiple(monkeypatch: pytest.MonkeyPatch) -> None:
    singles = single_rows()
    multiples = multiple_rows()

    def rows(kwargs: dict[str, Any]) -> list[PracticeCandidate]:
        return singles if kwargs['question_types'] == ['single_choice'] else multiples

    result, _calls = run_candidates(monkeypatch, rows)

    assert [item.question_id for item in result] == [item.question_id for item in singles + multiples]
    assert [item.max_score for item in result[:16]] == [Decimal(1)] * 16
    assert [item.max_score for item in result[16:]] == [Decimal(2)] * 17
    # 原题分值被固定快照覆盖，但候选行本身不可被改写
    assert singles[0].max_score == Decimal(3)
    assert multiples[0].max_score == Decimal(3)


def test_politics_candidates_forward_scope_filters_and_exclusions(monkeypatch: pytest.MonkeyPatch) -> None:
    obj = politics_obj(year_start=2010, year_end=2026, region='北京')
    result, calls = run_candidates(
        monkeypatch,
        lambda kwargs: single_rows() if kwargs['question_types'] == ['single_choice'] else multiple_rows(),
        obj=obj,
        point_ids={301, 201, 202},
    )

    assert len(result) == 33
    assert [call['knowledge_point_ids'] for call in calls] == [[201, 202, 301], [201, 202, 301]]
    assert [call['question_types'] for call in calls] == [['single_choice'], ['multiple_choice']]
    assert [call['limit'] for call in calls] == [16, 17]
    assert [call['exclude_question_ids'] for call in calls] == [[], sorted(item.question_id for item in single_rows())]
    for call in calls:
        assert call['user_id'] == 7
        assert call['source_type'] == 'custom'
        assert call['bank_id'] is None
        assert call['section_ids'] == []
        assert call['favorite_folder_id'] is None
        assert call['question_ids'] == []
        assert call['year_start'] == 2010
        assert call['year_end'] == 2026
        assert call['region'] == '北京'
        assert call['shuffle'] is True
        assert call['prioritize_unseen'] is True


def test_politics_candidates_reject_empty_resolved_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(errors.RequestError, match='所选抽题范围不可用，请返回重新选择'):
        run_candidates(monkeypatch, [], point_ids=set())


def short_single_rows(_kwargs: dict[str, Any]) -> list[PracticeCandidate]:
    return single_rows(15)


def short_multiple_rows(kwargs: dict[str, Any]) -> list[PracticeCandidate]:
    return multiple_rows(16) if kwargs['question_types'] == ['multiple_choice'] else single_rows()


@pytest.mark.parametrize(
    ('rows', 'message'),
    [
        (short_single_rows, '单选题不足16道'),
        (short_multiple_rows, '多选题不足17道'),
    ],
)
def test_politics_candidates_reject_short_question_type(
    monkeypatch: pytest.MonkeyPatch,
    rows: Any,
    message: str,
) -> None:
    with pytest.raises(errors.RequestError, match=message):
        run_candidates(monkeypatch, rows)


def test_politics_candidates_reject_duplicate_inside_batch(monkeypatch: pytest.MonkeyPatch) -> None:
    duplicates = [*single_rows(15), candidate(15)]

    with pytest.raises(errors.RequestError, match='单选题不足16道'):
        run_candidates(monkeypatch, lambda _kwargs: duplicates)


def test_politics_candidates_reject_question_already_used_by_single_choice(monkeypatch: pytest.MonkeyPatch) -> None:
    def rows(kwargs: dict[str, Any]) -> list[PracticeCandidate]:
        if kwargs['question_types'] == ['multiple_choice']:
            return [candidate(16), *multiple_rows(16)]
        return single_rows()

    with pytest.raises(errors.RequestError, match='多选题不足17道'):
        run_candidates(monkeypatch, rows)


def patch_create(
    monkeypatch: pytest.MonkeyPatch,
    *,
    singles: list[PracticeCandidate] | None = None,
    multiples: list[PracticeCandidate] | None = None,
    resolved: set[int] | None = None,
    existing: Any = None,
) -> dict[str, Any]:
    captured: dict[str, Any] = {'calls': [], 'resolve': []}
    single_candidates = singles if singles is not None else single_rows()
    multiple_candidates = multiples if multiples is not None else multiple_rows()

    def resolve_points(**kwargs: Any) -> set[int]:
        captured['resolve'].append(kwargs)
        return {201, 301} if resolved is None else resolved

    def get_by_key(*_args: Any, **_kwargs: Any) -> Any:
        return existing

    def get_candidates(_db: Any, **kwargs: Any) -> list[PracticeCandidate]:
        captured['calls'].append(kwargs)
        if kwargs['question_types'] == ['single_choice']:
            return single_candidates
        return multiple_candidates

    def create_session(_db: Any, values: dict[str, Any]) -> Any:
        captured['values'] = values
        return SimpleNamespace(id=1, session_key=values['session_key'])

    def create_items(_db: Any, **kwargs: Any) -> None:
        captured['items'] = kwargs['candidates']

    def get_detail(**_kwargs: Any) -> Any:
        return SimpleNamespace(session_key='created-session')

    monkeypatch.setattr(module.knowledge_service, 'resolve_point_ids', AsyncMock(side_effect=resolve_points))
    monkeypatch.setattr(module.knowledge_service, 'resolve_point_system_id', AsyncMock(return_value=11))
    monkeypatch.setattr(module.practice_session_dao, 'get_by_key', AsyncMock(side_effect=get_by_key))
    monkeypatch.setattr(PracticeService, '_politics_plan', fake_single_scope_plan, raising=False)
    monkeypatch.setattr(module.practice_session_item_dao, 'get_user_candidates', AsyncMock(side_effect=get_candidates))
    monkeypatch.setattr(module.practice_session_dao, 'create', AsyncMock(side_effect=create_session))
    monkeypatch.setattr(module.practice_session_item_dao, 'create_all', AsyncMock(side_effect=create_items))
    monkeypatch.setattr(PracticeService, 'get', AsyncMock(side_effect=get_detail))
    return captured


@pytest.mark.parametrize(
    ('singles', 'multiples', 'message'),
    [
        (single_rows(15), multiple_rows(), '单选题不足16道'),
        (single_rows(), multiple_rows(16), '多选题不足17道'),
    ],
)
def test_create_never_persists_incomplete_politics_paper(
    monkeypatch: pytest.MonkeyPatch,
    singles: list[PracticeCandidate],
    multiples: list[PracticeCandidate],
    message: str,
) -> None:
    captured = patch_create(monkeypatch, singles=singles, multiples=multiples)

    with pytest.raises(errors.RequestError, match=message):
        asyncio.run(PracticeService.create(db=None, user_id=7, obj=politics_obj()))

    assert 'values' not in captured
    assert 'items' not in captured


def test_create_never_persists_when_resolved_scope_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = patch_create(monkeypatch, resolved=set())

    with pytest.raises(errors.RequestError, match='所选抽题范围不可用'):
        asyncio.run(PracticeService.create(db=None, user_id=7, obj=politics_obj()))

    assert 'values' not in captured
    assert 'items' not in captured


def test_create_politics_practice_snapshots_profile_and_resolved_scope(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = patch_create(monkeypatch, resolved={201, 202, 301})

    result = asyncio.run(PracticeService.create(db=None, user_id=7, obj=politics_obj()))

    assert result.session_key == 'created-session'
    values = captured['values']
    assert values['total_items'] == 33
    assert values['mode'] == 'practice'
    assert values['source_type'] == 'knowledge_point'
    assert values['source_ref'].startswith('knowledge:')
    assert len(captured['items']) == 33
    assert [item.max_score for item in captured['items'][:16]] == [Decimal(1)] * 16
    assert [item.max_score for item in captured['items'][16:]] == [Decimal(2)] * 17

    delivery = values['delivery_config']
    assert delivery['shuffle'] is True
    assert delivery['paper_profile'] == 'kaoyan_politics'
    assert delivery['requested_limit'] == 33
    assert delivery['requested_duration_minutes'] is None
    assert delivery['selection_strategy'] == 'default'
    assert delivery['module_quotas'] == []

    snapshot = values['source_snapshot']
    assert snapshot['paper_profile'] == 'kaoyan_politics'
    assert snapshot['requested_source_type'] == 'custom'
    assert snapshot['bank_id'] is None
    assert snapshot['knowledge_system_id'] == 11
    assert snapshot['knowledge_point_ids'] == [201, 202]
    assert snapshot['resolved_knowledge_point_ids'] == [201, 202, 301]
    assert captured['resolve'][0]['include_descendants'] is True
    assert captured['resolve'][0]['system_id'] == 11


@pytest.mark.parametrize(('mode', 'expected_minutes'), [('practice', None), ('exam', 45)])
def test_create_politics_session_expiry_matches_mode(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    expected_minutes: int | None,
) -> None:
    fixed_now = datetime(2026, 5, 1, 8, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(module.timezone, 'now', lambda: fixed_now)
    captured = patch_create(monkeypatch)

    asyncio.run(PracticeService.create(db=None, user_id=7, obj=politics_obj(mode)))

    expires_time = captured['values']['expires_time']
    if expected_minutes is None:
        assert expires_time is None
    else:
        assert expires_time == fixed_now + timedelta(minutes=expected_minutes)


def matching_session(obj: CreatePracticeSessionParam) -> SimpleNamespace:
    return SimpleNamespace(
        user_id=7,
        mode=obj.mode,
        title_snapshot=obj.title,
        source_snapshot={
            'requested_source_type': obj.source_type,
            'bank_id': obj.bank_id,
            'section_id': obj.section_id,
            'favorite_folder_id': obj.favorite_folder_id,
            'question_ids': obj.question_ids,
            'knowledge_point_ids': obj.knowledge_point_ids,
            'knowledge_system_id': obj.knowledge_system_id,
        },
        delivery_config={
            'shuffle': obj.shuffle,
            'requested_limit': obj.limit,
            'requested_duration_minutes': obj.duration_minutes,
            'annotations_enabled': obj.annotations_enabled,
            'question_types': obj.question_types,
            'year_start': obj.year_start,
            'year_end': obj.year_end,
            'region': obj.region,
            'include_knowledge_descendants': obj.include_knowledge_descendants,
            'module_quotas': [item.model_dump() for item in obj.module_quotas],
            'selection_strategy': obj.selection_strategy,
            'paper_profile': obj.paper_profile,
        },
    )


def test_idempotent_match_distinguishes_paper_profile() -> None:
    obj = politics_obj()
    session = matching_session(obj)

    assert PracticeService._matches_create_request(session=session, user_id=7, obj=obj) is True

    session.delivery_config['paper_profile'] = None
    assert PracticeService._matches_create_request(session=session, user_id=7, obj=obj) is False


def test_create_rejects_reused_session_key_with_other_paper_profile(monkeypatch: pytest.MonkeyPatch) -> None:
    obj = politics_obj(session_key='politics_session_01')
    existing = matching_session(obj)
    existing.delivery_config['paper_profile'] = None

    monkeypatch.setattr(module.practice_session_dao, 'get_by_key', AsyncMock(return_value=existing))
    monkeypatch.setattr(
        module.practice_session_item_dao,
        'get_user_candidates',
        AsyncMock(side_effect=AssertionError('conflict must be detected before drawing candidates')),
    )

    with pytest.raises(errors.ConflictError, match='会话标识已被其他请求使用'):
        asyncio.run(PracticeService.create(db=None, user_id=7, obj=obj))


def test_create_reuses_matching_paper_session_without_redrawing(monkeypatch: pytest.MonkeyPatch) -> None:
    obj = politics_obj('exam', session_key='politics_exam_01')
    existing = matching_session(obj)
    expected = SimpleNamespace(session_key='politics_exam_01')

    monkeypatch.setattr(module.practice_session_dao, 'get_by_key', AsyncMock(return_value=existing))
    monkeypatch.setattr(
        module.practice_session_item_dao,
        'get_user_candidates',
        AsyncMock(side_effect=AssertionError('idempotent retry must not redraw')),
    )
    monkeypatch.setattr(PracticeService, 'get', AsyncMock(return_value=expected))

    assert asyncio.run(PracticeService.create(db=None, user_id=7, obj=obj)) is expected


def test_politics_report_keeps_profile_and_uses_item_scores(monkeypatch: pytest.MonkeyPatch) -> None:
    now = datetime(2026, 11, 1, 8, 0, tzinfo=timezone.utc)
    session = {
        'id': 1,
        'session_key': 'politics_report_01',
        'bank_id': None,
        'mode': 'exam',
        'source_type': 'knowledge_point',
        'title_snapshot': '考研政治模拟考试',
        'status': 'graded',
        'score': Decimal(34),
        'source_snapshot': {'paper_profile': 'kaoyan_politics', 'knowledge_point_ids': [201]},
        'started_time': now,
        'submitted_time': now + timedelta(minutes=20),
    }
    rows = [
        {
            'session_item_id': index + 1,
            'position': index,
            'question_id': index + 1,
            'bank_item_id': None,
            'section_id': None,
            'section_name': None,
            'response_status': 'graded',
            'is_correct': index >= 16,
            'duration_ms': 1000,
            'score': Decimal(2) if index >= 16 else Decimal(0),
            'max_score': Decimal(2) if index >= 16 else Decimal(1),
        }
        for index in range(33)
    ]
    monkeypatch.setattr(module.practice_session_dao, 'get_detail', AsyncMock(return_value=session))
    monkeypatch.setattr(module.practice_session_dao, 'get_report_items', AsyncMock(return_value=rows))

    report = asyncio.run(PracticeService.get_report(db=None, user_id=7, session_key=session['session_key']))

    assert report.source_snapshot['paper_profile'] == 'kaoyan_politics'
    assert report.total_score == Decimal(50)
    assert report.score == Decimal(34)
    assert report.correct_items == 17
    assert report.wrong_items == 16
