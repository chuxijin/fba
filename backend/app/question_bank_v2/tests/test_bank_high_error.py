"""试卷高频易错：阈值、有效样本、SQL 范围、目录与实际投递一致性。"""

import asyncio

from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest

from pydantic import ValidationError
from sqlalchemy import create_engine

from backend.app.question_bank_v2.crud.crud_bank_high_error import bank_high_error_dao
from backend.app.question_bank_v2.crud.crud_practice import PracticeCandidate
from backend.app.question_bank_v2.schema.practice import CreatePracticeSessionParam
from backend.app.question_bank_v2.service import practice_service as practice_module
from backend.app.question_bank_v2.service.analytics_service import AnalyticsService
from backend.app.question_bank_v2.service.bank_high_error_service import BankHighErrorService
from backend.app.question_bank_v2.service.practice_service import PracticeService
from backend.common.exception import errors


def row(question_id: int, **values: Any) -> dict[str, Any]:
    return {
        'question_id': question_id,
        'bank_item_id': question_id,
        'section_id': 11,
        'question_type': 'single_choice',
        'graded_count': 5,
        'correct_count': 5,
        'duration_count': 0,
        'avg_duration_ms': None,
        'score': 2,
        'settings': {'original': True},
        **values,
    }


@pytest.mark.parametrize(
    ['graded', 'correct', 'expected'], [[4, 0, False], [5, 2, True], [6, 3, False], [5, 3, False], [0, 0, False]]
)
def test_accuracy_strict_threshold_and_minimum_samples(graded: int, correct: int, *, expected: bool) -> None:
    selected = BankHighErrorService.select_rows([row(1, graded_count=graded, correct_count=correct)])
    assert bool(selected) is expected


def test_slow_strict_boundary_and_independent_sample_count() -> None:
    exact = [row(1, duration_count=5, avg_duration_ms=150), row(2, duration_count=50, avg_duration_ms=50)]
    assert BankHighErrorService.select_rows(exact) == []  # 基线100，恰好1.5倍不入选；等权而非按作答量加权。
    exact[0]['avg_duration_ms'] = 151
    exact[1]['avg_duration_ms'] = 49
    exact[0]['graded_count'] = 0
    selected = BankHighErrorService.select_rows(exact)
    assert [item['question_id'] for item in selected] == [1]
    assert selected[0]['slow'] is True
    assert selected[0]['correct_rate'] is None  # 耗时指标不要求已有5次判分。
    exact[0]['duration_count'] = 4
    assert BankHighErrorService.select_rows(exact) == []


def test_baselines_do_not_mix_chapters_types_or_insufficient_samples() -> None:
    rows = [
        row(1, duration_count=5, avg_duration_ms=100),
        row(2, section_id=12, duration_count=5, avg_duration_ms=1),
        row(3, question_type='multiple_choice', duration_count=5, avg_duration_ms=1),
        row(4, duration_count=4, avg_duration_ms=1),
        row(5, graded_count=None, correct_count=None),
    ]
    assert BankHighErrorService.select_rows(rows) == []


def test_both_reasons_only_select_once() -> None:
    selected = BankHighErrorService.select_rows([
        row(1, correct_count=1, duration_count=5, avg_duration_ms=200),
        row(2, duration_count=5, avg_duration_ms=20),
    ])
    assert len(selected) == 1
    assert selected[0]['low_accuracy'] is selected[0]['slow'] is True
    assert selected[0]['correct_rate'] == pytest.approx(0.2)


@pytest.mark.parametrize(
    'overrides',
    [
        {'source_type': 'wrong'},
        {'source_type': 'custom', 'question_ids': [1]},
        {'mode': 'exam'},
        {'mode': 'memorize'},
        {'shuffle': True},
        {'question_types': ['single_choice']},
        {'knowledge_point_ids': [1]},
        {'year_start': 2020},
        {'year_end': 2026},
        {'region': '北京'},
    ],
)
def test_strategy_rejects_other_sources_modes_and_filters(overrides: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        CreatePracticeSessionParam(bank_id=1, selection_strategy='bank_high_error', **overrides)


class MemorySession:
    def __init__(self, connection: Any) -> None:
        self.connection = connection

    async def execute(self, statement: Any) -> Any:
        return self.connection.execute(statement)


@pytest.fixture
def db() -> Iterator[MemorySession]:
    engine = create_engine('sqlite://')
    with engine.connect() as connection:
        tables = {
            'question': (
                'id INTEGER, status TEXT, deleted INTEGER, visibility TEXT, owner_id INTEGER, question_type TEXT'
            ),
            'bank_item': (
                'id INTEGER, bank_revision_id INTEGER, question_id INTEGER, section_id INTEGER, score NUMERIC, '
                'settings JSON, sort_order INTEGER, deleted INTEGER, is_active BOOLEAN'
            ),
            'bank_section': 'id INTEGER, bank_revision_id INTEGER, deleted INTEGER',
            'question_statistics': 'question_id INTEGER, graded_count INTEGER, correct_count INTEGER, deleted INTEGER',
            'question_attempt': (
                'question_id INTEGER, user_id INTEGER, duration_ms INTEGER, deleted INTEGER, grading_result JSON'
            ),
        }
        for name, columns in tables.items():
            connection.exec_driver_sql(f'CREATE TABLE qbank_v2_{name} ({columns})')
        connection.exec_driver_sql('INSERT INTO qbank_v2_bank_section VALUES (11,1,0),(12,1,0),(13,1,1),(14,2,0)')
        for qid in range(1, 12):
            visibility = 'private' if qid in {4, 5} else 'public'
            status = 'archived' if qid == 6 else 'active'
            owner = 7 if qid == 5 else 8
            connection.exec_driver_sql(
                'INSERT INTO qbank_v2_question VALUES (?,?,0,?,?,?)',
                (qid, status, visibility, owner, 'single_choice'),
            )
            section = {7: 13, 8: 14, 10: None}.get(qid, 11)
            connection.exec_driver_sql(
                'INSERT INTO qbank_v2_bank_item VALUES (?,?,?,?,2,?,0,0,?)',
                (qid, 2 if qid == 9 else 1, qid, section, '{}', qid != 11),
            )
            if qid != 3:
                connection.exec_driver_sql('INSERT INTO qbank_v2_question_statistics VALUES (?,5,1,?)', (qid, qid == 2))
        # 同题重复编排应只占首次章节，不能改变时长样本量。
        connection.exec_driver_sql("INSERT INTO qbank_v2_bank_item VALUES (101,1,1,12,3,'{}',1,0,1)")
        for index in range(5):
            connection.exec_driver_sql(
                "INSERT INTO qbank_v2_question_attempt VALUES (1,?,100,0,'{}')", (7 if index < 2 else 8,)
            )
        connection.exec_driver_sql(
            'INSERT INTO qbank_v2_question_attempt VALUES (1,8,99999,0,\'{"origin":"external_practice"}\'),'
            "(1,8,99999,1,'{}'),(1,8,0,0,'{}'),(1,8,NULL,0,'{}'),(9,8,99999,0,'{}')"
        )
        yield MemorySession(connection)
    engine.dispose()


def test_sql_current_visible_unique_questions_and_valid_global_durations(db: MemorySession) -> None:
    rows = asyncio.run(bank_high_error_dao.get_rows(db, revision_id=1, user_id=7))
    assert [item['question_id'] for item in rows] == [10, 1, 2, 3, 5]
    first = next(item for item in rows if item['question_id'] == 1)
    assert first['bank_item_id'] == 1
    assert first['section_id'] == 11
    assert first['duration_count'] == 5
    assert float(first['avg_duration_ms']) == pytest.approx(100)
    selected = BankHighErrorService.select_rows(rows)
    assert [item['question_id'] for item in selected] == [10, 1, 5]
    assert rows[2]['graded_count'] is None  # 已删除统计不能被当作0%正确率。


def patch_rows_and_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        bank_high_error_dao,
        'get_rows',
        AsyncMock(
            return_value=[
                row(1, section_id=11, correct_count=1),
                row(2, section_id=12, correct_count=2),
                row(3, section_id=None, correct_count=0),
                row(4, section_id=12),
            ]
        ),
    )
    sections = [
        SimpleNamespace(id=10, name='父', parent_id=None, depth=0, sort_order=0),
        SimpleNamespace(id=11, name='子一', parent_id=10, depth=1, sort_order=0),
        SimpleNamespace(id=12, name='子二', parent_id=10, depth=1, sort_order=1),
        SimpleNamespace(id=13, name='空', parent_id=None, depth=0, sort_order=1),
    ]
    from backend.app.question_bank_v2.service.bank_high_error_service import bank_section_dao

    monkeypatch.setattr(bank_section_dao, 'get_all', AsyncMock(return_value=sections))
    monkeypatch.setattr(bank_section_dao, 'resolve_ids_with_descendants', AsyncMock(return_value=[10, 11, 12]))
    monkeypatch.setattr(AnalyticsService, '_get_bank_context', AsyncMock(return_value=(None, SimpleNamespace(id=1))))


def test_tree_and_delivery_use_same_selection_and_preserve_reason_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_rows_and_sections(monkeypatch)
    tree = asyncio.run(BankHighErrorService.get_sections(db=None, user_id=7, bank_id=1))
    candidates = asyncio.run(
        BankHighErrorService.get_candidates(db=None, user_id=7, revision_id=1, section_id=10, limit=500)
    )
    assert tree.total_count == tree.low_accuracy_count == 3
    assert tree.slow_count == 0
    assert tree.unsectioned_count == 1
    assert len(tree.sections) == 1
    assert tree.sections[0].question_count == len(candidates) == 2
    assert [node.question_count for node in tree.sections[0].children] == [1, 1]
    assert [candidate.question_id for candidate in candidates] == [1, 2]
    assert candidates[0].display_config['original'] is True
    assert candidates[0].display_config['bank_high_error']['low_accuracy'] is True
    AnalyticsService._get_bank_context.assert_awaited_once_with(db=None, user_id=7, bank_id=1)
    limited = asyncio.run(
        BankHighErrorService.get_candidates(db=None, user_id=7, revision_id=1, section_id=None, limit=1)
    )
    assert [candidate.question_id for candidate in limited] == [1]


def test_sections_deny_access_before_reading_statistics(monkeypatch: pytest.MonkeyPatch) -> None:
    patch_rows_and_sections(monkeypatch)
    monkeypatch.setattr(AnalyticsService, '_get_bank_context', AsyncMock(side_effect=errors.ForbiddenError(msg='会员')))
    with pytest.raises(errors.ForbiddenError):
        asyncio.run(BankHighErrorService.get_sections(db=None, user_id=7, bank_id=1))
    bank_high_error_dao.get_rows.assert_not_awaited()


def test_specialty_session_is_not_normal_resumable_scope() -> None:
    rows = [
        {'id': 1, 'mode': 'practice', 'session_key': 'normal', 'source_snapshot': {}, 'delivery_config': {}},
        {
            'id': 2,
            'mode': 'practice',
            'session_key': 'specialty',
            'source_snapshot': {},
            'delivery_config': {'selection_strategy': 'bank_high_error'},
        },
    ]
    result = Mock()
    result.mappings.return_value.all.return_value = rows
    scopes = asyncio.run(
        AnalyticsService._get_resumable_scopes(
            db=SimpleNamespace(execute=AsyncMock(return_value=result)), user_id=7, bank_id=1
        )
    )
    assert len(scopes) == 1
    assert scopes[0].session_keys == {'practice': 'normal'}


@pytest.mark.parametrize('allowed', [True, False])
def test_create_routes_new_strategy_after_access_check(monkeypatch: pytest.MonkeyPatch, *, allowed: bool) -> None:
    from backend.app.question_bank_v2.service.bank_high_error_service import bank_high_error_service

    bank = SimpleNamespace(id=1, current_revision_id=2)
    decision = SimpleNamespace(allowed=allowed, reason_code='test')
    monkeypatch.setattr(
        practice_module.bank_access_service, 'ensure_bank_access', AsyncMock(return_value=(bank, decision))
    )
    monkeypatch.setattr(practice_module.BankAccessService, '_deny_message', lambda _decision: '会员')
    monkeypatch.setattr(
        practice_module.bank_revision_dao,
        'get',
        AsyncMock(return_value=SimpleNamespace(id=2, status='published', name='卷')),
    )
    monkeypatch.setattr(PracticeService, '_get_idempotent_session', AsyncMock(return_value=None))
    candidate = PracticeCandidate(question_id=1, bank_item_id=1, max_score=2, display_config={})
    select = AsyncMock(return_value=[candidate])
    monkeypatch.setattr(bank_high_error_service, 'get_candidates', select)
    normal = AsyncMock()
    monkeypatch.setattr(practice_module.practice_session_item_dao, 'get_candidates', normal)
    create = AsyncMock(return_value=SimpleNamespace(id=1, session_key='new'))
    monkeypatch.setattr(practice_module.practice_session_dao, 'create', create)
    items = AsyncMock()
    monkeypatch.setattr(practice_module.practice_session_item_dao, 'create_all', items)
    monkeypatch.setattr(PracticeService, 'get', AsyncMock(return_value='detail'))
    obj = CreatePracticeSessionParam(bank_id=1, selection_strategy='bank_high_error')
    if not allowed:
        with pytest.raises(errors.ForbiddenError):
            asyncio.run(PracticeService.create(db=None, user_id=7, obj=obj))
        select.assert_not_awaited()
        create.assert_not_awaited()
        return
    assert asyncio.run(PracticeService.create(db=None, user_id=7, obj=obj)) == 'detail'
    select.assert_awaited_once_with(db=None, user_id=7, revision_id=2, section_id=None, limit=500)
    normal.assert_not_awaited()
    assert create.await_args.args[1]['delivery_config']['selection_strategy'] == 'bank_high_error'
    assert items.await_args.kwargs['candidates'] == [candidate]
