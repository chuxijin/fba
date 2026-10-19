"""知识点自由组题的参数、真实 SQL 作用域与会话创建回归。"""

import asyncio

from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from pydantic import ValidationError
from sqlalchemy import create_engine

from backend.app.question_bank_v2.crud.crud_practice import practice_session_item_dao
from backend.app.question_bank_v2.schema.practice import CreatePracticeSessionParam
from backend.app.question_bank_v2.service import practice_service as module
from backend.app.question_bank_v2.service.practice_service import PracticeService


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
                'id INTEGER, default_score NUMERIC, status TEXT, deleted INTEGER, visibility TEXT, '
                'owner_id INTEGER, question_type TEXT'
            ),
            'question_knowledge_point': 'question_id INTEGER, knowledge_point_id INTEGER, deleted INTEGER',
            'wrong_question_state': 'user_id INTEGER, question_id INTEGER, deleted INTEGER, last_wrong_response JSON',
            'question_review': (
                'id INTEGER, user_id INTEGER, question_id INTEGER, summary TEXT, review_data JSON, '
                'reviewed_time DATETIME, event_type TEXT, deleted INTEGER'
            ),
            'question_review_tag': 'review_id INTEGER, tag_id INTEGER, deleted INTEGER',
            'review_tag': 'id INTEGER, name TEXT, deleted INTEGER',
            'question_review_knowledge_point': 'review_id INTEGER, knowledge_point_id INTEGER, deleted INTEGER',
            'knowledge_point': 'id INTEGER, name TEXT, deleted INTEGER',
            'question_attempt': (
                'id INTEGER, question_id INTEGER, user_id INTEGER, attempt_no INTEGER, response_data JSON, '
                'submitted_time DATETIME, is_correct BOOLEAN, deleted INTEGER'
            ),
            'bank_item': (
                'id INTEGER, bank_revision_id INTEGER, question_id INTEGER, exam_year INTEGER, '
                'is_active BOOLEAN, deleted INTEGER'
            ),
            'bank_revision': 'id INTEGER, bank_id INTEGER, status TEXT, deleted INTEGER, name TEXT, description TEXT',
            'bank': (
                'id INTEGER, name TEXT, code TEXT, description TEXT, current_revision_id INTEGER, '
                'status TEXT, deleted INTEGER'
            ),
        }
        for name, columns in tables.items():
            connection.exec_driver_sql(f'CREATE TABLE qbank_v2_{name} ({columns})')
        for sql in (
            "INSERT INTO qbank_v2_question VALUES (1,2,'active',0,'public',NULL,'single_choice'),"
            "(2,2,'active',0,'public',NULL,'multiple_choice'),(3,2,'active',0,'private',8,'single_choice'),"
            "(4,2,'active',0,'private',7,'single_choice'),(5,2,'disabled',0,'public',NULL,'single_choice'),"
            "(6,2,'active',1,'public',NULL,'single_choice'),(7,2,'archived',0,'public',NULL,'single_choice'),"
            "(8,2,'active',0,'public',NULL,'single_choice')",
            'INSERT INTO qbank_v2_question_knowledge_point VALUES (1,201,0),(1,301,0),(2,301,0),'
            '(3,201,0),(4,401,0),(5,201,0),(6,201,0),(7,201,0),(8,999,0),(8,201,1)',
            "INSERT INTO qbank_v2_bank VALUES (1,'广西真题','gx','广西',11,'active',0),"
            "(2,'贵州真题','gz','贵州',21,'active',0)",
            "INSERT INTO qbank_v2_bank_revision VALUES (11,1,'published',0,'广西真题','广西'),"
            "(12,1,'retired',0,'广西旧版','广西'),(21,2,'published',0,'贵州真题','贵州')",
            'INSERT INTO qbank_v2_bank_item VALUES (1,11,1,2026,1,0),(2,11,2,2020,1,0),'
            '(3,21,4,2025,1,0),(4,12,2,2026,1,0)',
        ):
            connection.exec_driver_sql(sql)
        yield MemorySession(connection)
    engine.dispose()


def candidates(db: MemorySession, **kwargs: Any) -> list[int]:
    options = {
        'user_id': 7, 'source_type': 'custom', 'bank_id': None, 'section_ids': [],
        'favorite_folder_id': None, 'question_ids': [], 'knowledge_point_ids': [201, 301, 401],
        'question_types': [], 'year_start': None, 'year_end': None, 'shuffle': False, 'limit': 20,
        **kwargs,
    }
    rows = asyncio.run(practice_session_item_dao.get_user_candidates(db, **options))
    return [row.question_id for row in rows]


def test_knowledge_source_is_valid_without_a_bank_or_explicit_question_ids() -> None:
    obj = CreatePracticeSessionParam(source_type='custom', knowledge_point_ids=[201, 201], knowledge_system_id=11)
    assert obj.knowledge_point_ids == [201]
    assert obj.question_ids == []
    source_type, source_ref = PracticeService._build_source_context(obj=obj)
    assert source_type == 'knowledge_point'
    assert source_ref.startswith('knowledge:')


def test_free_composition_cannot_be_unbounded() -> None:
    with pytest.raises(ValidationError):
        CreatePracticeSessionParam(source_type='custom')


def test_candidates_deduplicate_overlapping_points_and_exclude_unavailable_questions(db: MemorySession) -> None:
    assert candidates(db) == [1, 2, 4]
    assert candidates(db, knowledge_point_ids=[301]) == [1, 2]
    assert candidates(db, knowledge_point_ids=[]) == []


@pytest.mark.parametrize(('filters', 'expected'), [
    ({'year_start': 2024, 'year_end': 2026}, [1, 4]),
    ({'bank_id': 1}, [1, 2]),
    ({'region': '贵州'}, [4]),
    ({'question_types': ['multiple_choice']}, [2]),
])
def test_knowledge_composition_preserves_filters(
    db: MemorySession, filters: dict[str, Any], expected: list[int]
) -> None:
    assert candidates(db, **filters) == expected


def test_explicit_question_order_is_preserved(db: MemorySession) -> None:
    assert candidates(db, question_ids=[2, 1], knowledge_point_ids=[]) == [2, 1]


def test_random_selection_is_limited_and_stays_in_scope(db: MemorySession) -> None:
    result = candidates(db, shuffle=True, limit=2)
    assert len(result) == 2
    assert set(result) <= {1, 2, 4}


def mark_attempted(
    db: MemorySession,
    attempts: list[tuple[int, str]],
    *,
    user_id: int = 7,
) -> None:
    """写入真实作答事实，供「未做优先」回归使用"""
    for index, (question_id, submitted_time) in enumerate(attempts, start=1):
        db.connection.exec_driver_sql(
            'INSERT INTO qbank_v2_question_attempt '
            '(id, question_id, user_id, attempt_no, response_data, submitted_time, is_correct, deleted) '
            f"VALUES ({index}, {question_id}, {user_id}, 1, '{{}}', '{submitted_time}', 1, 0)"
        )


def test_unseen_questions_are_delivered_before_attempted_ones(db: MemorySession) -> None:
    mark_attempted(db, [(1, '2026-01-01 10:00:00'), (2, '2026-01-05 10:00:00')])
    for _ in range(5):
        result = candidates(db, shuffle=True, limit=2, prioritize_unseen=True)
        assert len(result) == 2
        assert result[0] == 4
        assert result[1] in {1, 2}


def test_unseen_priority_stops_once_new_questions_run_out(db: MemorySession) -> None:
    mark_attempted(db, [(1, '2026-01-01 10:00:00'), (2, '2026-01-05 10:00:00')])
    assert candidates(db, shuffle=True, limit=1, prioritize_unseen=True) == [4]


def test_attempted_questions_are_refilled_by_least_recently_practiced(db: MemorySession) -> None:
    mark_attempted(db, [(1, '2026-01-01 10:00:00'), (2, '2026-01-05 10:00:00')])
    assert candidates(db, shuffle=True, limit=3, prioritize_unseen=True) == [4, 1, 2]


def test_priority_ignores_other_users_attempts(db: MemorySession) -> None:
    mark_attempted(db, [(4, '2026-01-03 10:00:00')])
    mark_attempted(db, [(1, '2026-01-01 10:00:00'), (2, '2026-01-02 10:00:00')], user_id=99)
    assert sorted(candidates(db, shuffle=True, limit=2, prioritize_unseen=True)) == [1, 2]


def test_random_selection_without_priority_keeps_any_candidates(db: MemorySession) -> None:
    mark_attempted(db, [(1, '2026-01-01 10:00:00'), (2, '2026-01-05 10:00:00')])
    result = candidates(db, shuffle=True, limit=2)
    assert len(result) == 2
    assert set(result) <= {1, 2, 4}


def test_create_forwards_unseen_priority_only_for_shuffled_practice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    forwarded: list[bool] = []

    def resolve_points(**_kwargs: Any) -> set[int]:
        return {201}

    def resolve_system_id(**_kwargs: Any) -> int:
        return 11

    def get_candidates(_db: Any, **kwargs: Any) -> list[Any]:
        forwarded.append(bool(kwargs['prioritize_unseen']))
        return [SimpleNamespace(question_id=1)]

    def create_session(_db: Any, values: dict[str, Any]) -> Any:
        return SimpleNamespace(id=1, session_key=values['session_key'])

    def create_items(_db: Any, **_kwargs: Any) -> None:
        return None

    def get_detail(**_kwargs: Any) -> Any:
        return SimpleNamespace(session_key='k')

    monkeypatch.setattr(module.knowledge_service, 'resolve_point_ids', AsyncMock(side_effect=resolve_points))
    monkeypatch.setattr(module.knowledge_service, 'resolve_point_system_id', AsyncMock(side_effect=resolve_system_id))
    monkeypatch.setattr(PracticeService, '_get_idempotent_session', AsyncMock(return_value=None))
    monkeypatch.setattr(module.practice_session_item_dao, 'get_user_candidates', AsyncMock(side_effect=get_candidates))
    monkeypatch.setattr(module.practice_session_dao, 'create', AsyncMock(side_effect=create_session))
    monkeypatch.setattr(module.practice_session_item_dao, 'create_all', AsyncMock(side_effect=create_items))
    monkeypatch.setattr(PracticeService, 'get', AsyncMock(side_effect=get_detail))
    for shuffle, expected in ((True, True), (False, False)):
        asyncio.run(
            PracticeService.create(
                db=None,
                user_id=7,
                obj=CreatePracticeSessionParam(
                    source_type='custom',
                    knowledge_point_ids=[201],
                    knowledge_system_id=11,
                    shuffle=shuffle,
                    limit=20,
                ),
            )
        )
        assert forwarded[-1] is expected


def test_create_knowledge_session_resolves_descendants_and_records_knowledge_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: dict[str, Any] = {}

    def resolve_points(**kwargs: Any) -> set[int]:
        assert kwargs['point_ids'] == [201]
        assert kwargs['include_descendants'] is True
        assert kwargs['system_id'] == 11
        return {201, 301, 401}

    def get_candidates(db: Any, **kwargs: Any) -> list[Any]:
        assert kwargs['knowledge_point_ids'] == [201, 301, 401]
        assert kwargs['question_ids'] == []
        return [SimpleNamespace(question_id=1)]

    def create_session(db: Any, values: dict[str, Any]) -> Any:
        recorded.update(values)
        return SimpleNamespace(id=1, session_key=values['session_key'])

    def create_items(db: Any, **kwargs: Any) -> None:
        assert kwargs['candidates'][0].question_id == 1

    def get_detail(**kwargs: Any) -> Any:
        return SimpleNamespace(session_key=kwargs['session_key'])

    monkeypatch.setattr(module.knowledge_service, 'resolve_point_ids', AsyncMock(side_effect=resolve_points))
    monkeypatch.setattr(PracticeService, '_get_idempotent_session', AsyncMock(return_value=None))
    monkeypatch.setattr(module.practice_session_item_dao, 'get_user_candidates', AsyncMock(side_effect=get_candidates))
    monkeypatch.setattr(module.practice_session_dao, 'create', AsyncMock(side_effect=create_session))
    monkeypatch.setattr(module.practice_session_item_dao, 'create_all', AsyncMock(side_effect=create_items))
    monkeypatch.setattr(PracticeService, 'get', AsyncMock(side_effect=get_detail))
    obj = CreatePracticeSessionParam(
        source_type='custom', knowledge_point_ids=[201], knowledge_system_id=11,
        title='知识点练习', mode='memorize', shuffle=True, limit=20,
    )
    result = asyncio.run(PracticeService.create(db=None, user_id=7, obj=obj))
    assert result.session_key == recorded['session_key']
    assert recorded['source_type'] == 'knowledge_point'
    assert recorded['mode'] == 'memorize'
    assert recorded['source_snapshot']['resolved_knowledge_point_ids'] == [201, 301, 401]


class _ProbeBoundResult:
    def one(self) -> tuple[int, int]:
        return (1, 100)


class _ProbeEmptyResult:
    def scalars(self) -> '_ProbeEmptyResult':
        return self

    def all(self) -> list[Any]:
        return []


class _StatementProbe:
    """只编译不执行，用于校验两阶段抽样的 SQL 形态"""

    def __init__(self) -> None:
        self.statements: list[str] = []

    async def execute(self, statement: Any) -> Any:
        self.statements.append(str(statement.compile(compile_kwargs={'literal_binds': True})))
        return _ProbeBoundResult() if len(self.statements) == 1 else _ProbeEmptyResult()


def test_bank_selection_puts_priority_expression_into_distinct_select_list() -> None:
    probe = _StatementProbe()
    asyncio.run(
        practice_session_item_dao.get_candidates(
            probe,
            bank_revision_id=11,
            section_id=None,
            knowledge_point_ids=[],
            question_types=[],
            year_start=None,
            year_end=None,
            shuffle=True,
            limit=2,
            user_id=7,
            prioritize_unseen=True,
        )
    )
    assert len(probe.statements) == 4
    unseen_sql, refill_sql = probe.statements[1], probe.statements[3]
    assert 'EXISTS' in unseen_sql
    assert 'qbank_v2_question_attempt' in unseen_sql
    # DISTINCT 查询必须把排序表达式写进选择列表，否则 PostgreSQL 会直接报错
    assert refill_sql.startswith('SELECT DISTINCT')
    assert refill_sql.index('last_submitted_time') < refill_sql.index('ORDER BY')
