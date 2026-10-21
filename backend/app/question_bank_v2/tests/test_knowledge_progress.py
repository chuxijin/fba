import asyncio

from collections.abc import Iterator
from contextlib import asynccontextmanager
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest

from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql

from backend.app.question_bank_v2.crud.crud_knowledge import knowledge_point_dao
from backend.app.question_bank_v2.service import knowledge_service as service_module
from backend.app.question_bank_v2.service.knowledge_service import KnowledgeService
from backend.common.exception import errors


class MemorySession:
    def __init__(self, connection: Any) -> None:
        self.connection = connection
        self.statements: list[Any] = []

    async def execute(self, statement: Any) -> Any:
        self.statements.append(statement)
        return self.connection.execute(statement)


def point(point_id: int, parent_id: int | None) -> Any:
    return SimpleNamespace(
        id=point_id,
        parent_id=parent_id,
        system_id=3,
        code=str(point_id),
        name=str(point_id),
        path=None,
        depth=0,
        sort_order=point_id,
        description=None,
    )


@pytest.fixture
def db() -> Iterator[MemorySession]:
    engine = create_engine('sqlite://')
    with engine.connect() as connection:
        for name, columns in {
            'question_knowledge_point': 'question_id INTEGER, knowledge_point_id INTEGER, deleted INTEGER',
            'bank_item': (
                'id INTEGER, question_id INTEGER, bank_revision_id INTEGER, is_active BOOLEAN, deleted INTEGER'
            ),
            'user_bank_item_progress': (
                'id INTEGER, user_id INTEGER, question_id INTEGER, bank_item_id INTEGER, '
                'last_is_correct BOOLEAN, last_answered_time DATETIME, deleted INTEGER'
            ),
            'user_question_mastery': (
                'id INTEGER, user_id INTEGER, question_id INTEGER, state TEXT, mastery_score NUMERIC, deleted INTEGER'
            ),
        }.items():
            connection.exec_driver_sql(f'CREATE TABLE qbank_v2_{name} ({columns})')
        for sql in (
            'INSERT INTO qbank_v2_question_knowledge_point VALUES '
            '(1,1,0),(1,2,0),(1,4,0),(2,2,0),(2,3,0),(3,4,0),(4,1,0),'
            '(5,10,0),(6,99,0),(7,3,1),(8,3,0),(9,3,0),(10,3,0),(11,3,0)',
            'INSERT INTO qbank_v2_bank_item VALUES '
            '(101,1,11,1,0),(201,1,21,1,0),(102,2,11,1,0),(202,2,21,1,0),'
            '(103,3,11,1,0),(104,4,11,0,0),(105,5,11,1,0),(106,6,11,1,0),'
            '(107,7,11,1,0),(108,8,11,1,1),(109,9,11,1,0),(110,10,11,1,0),'
            '(111,11,11,1,0),(211,11,21,1,0)',
            'INSERT INTO qbank_v2_user_bank_item_progress VALUES '
            "(1,7,1,101,1,'2026-01-01',0),(2,7,1,201,0,'2026-01-02',0),"
            "(3,7,2,102,1,'2026-01-01',0),(4,7,2,202,0,'2026-01-02',0),"
            "(5,7,3,103,NULL,'2026-01-01',0),(6,7,9,109,1,'2026-01-01',1),"
            "(7,8,10,110,1,'2026-01-01',0),(8,7,11,111,1,'2026-01-01',0),"
            "(9,7,11,211,0,'2026-01-02',0),(10,7,5,105,1,'2026-01-02',0)",
            'INSERT INTO qbank_v2_user_question_mastery VALUES '
            "(1,7,1,'mastered',0.8,0),(2,7,2,'learning',0.2,0),(3,7,3,'mastered',0.9,0),"
            "(4,7,9,'mastered',1,1),(5,7,10,'learning',0.4,0),(6,7,11,'learning',0.5,0),"
            "(7,8,9,'mastered',1,0),(8,7,5,'mastered',1,0)",
        ):
            connection.exec_driver_sql(sql)
        yield MemorySession(connection)
    engine.dispose()


def progress(db: MemorySession, revision_id: int | None = None, **kwargs: Any) -> dict[int, dict[str, Any]]:
    return asyncio.run(
        knowledge_point_dao.get_progress(
            db,
            points=[point(1, None), point(2, 1), point(3, 1), point(4, 2)],
            bank_revision_id=revision_id,
            user_id=kwargs.get('user_id', 7),
        )
    )


def test_cross_bank_counts_deduplicate_overlapping_points_and_bank_items(db: MemorySession) -> None:
    result = progress(db)
    assert result[1]['question_count'] == result[0]['question_count'] == 6
    assert result[1]['direct_question_count'] == 1
    assert result[2]['question_count'] == 3
    assert result[3]['question_count'] == 4
    assert result[4]['question_count'] == 2
    assert result[1]['answered_count'] == 4
    assert result[1]['correct_count'] == 0
    assert result[1]['mastered_count'] == 2
    assert result[1]['mastery_sample_count'] == 5
    assert result[1]['mastery_sum'] == Decimal('2.8000')
    assert len(db.statements) == 3
    assert set(result) == {0, 1, 2, 3, 4}


@pytest.mark.parametrize(('revision_id', 'count', 'answered', 'correct'), [(11, 6, 4, 3), (21, 3, 3, 0)])
def test_bank_scope_preserves_item_progress(
    db: MemorySession, revision_id: int, count: int, answered: int, correct: int
) -> None:
    root = progress(db, revision_id)[1]
    assert (root['question_count'], root['answered_count'], root['correct_count']) == (count, answered, correct)


def test_other_users_and_deleted_progress_do_not_leak(db: MemorySession) -> None:
    root = progress(db, user_id=8)[1]
    assert root['answered_count'] == root['correct_count'] == 1
    assert root['mastered_count'] == 1
    assert root['mastery_sample_count'] == 1


def test_empty_subtree_skips_all_statistics_queries(db: MemorySession) -> None:
    result = asyncio.run(knowledge_point_dao.get_progress(db, points=[], bank_revision_id=None, user_id=7))
    assert result == {}
    assert db.statements == []


def test_empty_points_render_zero_counts(db: MemorySession) -> None:
    points = [point(1, None), point(20, 1)]
    result = asyncio.run(knowledge_point_dao.get_progress(db, points=points, bank_revision_id=999, user_id=7))
    tree = KnowledgeService._build_tree(points=points, progress=result, root_id=1)
    assert tree[0].question_count == tree[0].answered_count == tree[0].mastered_count == 0
    assert tree[0].children[0].question_count == 0


def test_latest_progress_uses_stable_tie_break_and_ignores_inactive_items(db: MemorySession) -> None:
    db.connection.exec_driver_sql(
        "UPDATE qbank_v2_user_bank_item_progress SET last_answered_time='2026-01-01' WHERE question_id=1"
    )
    assert progress(db)[1]['correct_count'] == 0  # 同时作答时，较大进度 ID 胜出。
    db.connection.exec_driver_sql('UPDATE qbank_v2_bank_item SET is_active=0 WHERE id=201')
    assert progress(db)[1]['correct_count'] == 1


def test_database_only_returns_node_aggregates(db: MemorySession) -> None:
    progress(db)
    for statement in db.statements:
        rows = db.connection.execute(statement).mappings().all()
        assert len(rows) <= 5
        assert 'item_id' not in statement.selected_columns.keys()
        sql = str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={'literal_binds': True}))
        assert 'knowledge_point_id IN (1, 2, 3, 4)' in sql


def test_subtree_loading_is_scoped_before_statistics(monkeypatch: pytest.MonkeyPatch) -> None:
    system = SimpleNamespace(
        id=3, domain_category_id=1, code='xingce', name='行测', version='default', description=None, status='active'
    )
    points = [point(1, None), point(2, 1)]
    load_points = AsyncMock(return_value=points)
    get_counts = AsyncMock(return_value={1: {'question_count': 6}})
    get_progress = AsyncMock(return_value={})
    request_db = SimpleNamespace(bind=None)
    public_db = SimpleNamespace()

    @asynccontextmanager
    async def public_session(**_kwargs: Any) -> Any:
        yield public_db

    async def uncached(*_args: Any, factory: Any) -> Any:
        return await factory()

    monkeypatch.setattr(service_module, 'async_db_session', public_session)
    monkeypatch.setattr(service_module.public_knowledge_cache, 'get', uncached)
    monkeypatch.setattr(service_module.knowledge_system_dao, 'get', AsyncMock(return_value=system))
    monkeypatch.setattr(service_module.knowledge_point_dao, 'get_all', load_points)
    monkeypatch.setattr(service_module.knowledge_point_dao, 'get_question_counts', get_counts)
    monkeypatch.setattr(service_module.knowledge_point_dao, 'get_user_progress', get_progress)
    result = asyncio.run(KnowledgeService.get_tree(db=request_db, user_id=7, system_id=3, root_id=1))
    load_points.assert_awaited_once_with(public_db, 3, root_id=1)
    get_counts.assert_awaited_once_with(public_db, points=points, bank_revision_id=None)
    assert get_progress.await_args.kwargs['user_id'] == 7
    assert [item.id for item in get_progress.await_args.kwargs['points']] == [1, 2]
    assert result.total_question_count == 6
    assert [node.id for node in result.points] == [1]


def test_invalid_subtree_is_rejected_before_statistics(monkeypatch: pytest.MonkeyPatch) -> None:
    @asynccontextmanager
    async def public_session(**_kwargs: Any) -> Any:
        yield None

    async def uncached(*_args: Any, factory: Any) -> Any:
        return await factory()

    monkeypatch.setattr(service_module, 'async_db_session', public_session)
    monkeypatch.setattr(service_module.public_knowledge_cache, 'get', uncached)
    monkeypatch.setattr(service_module.knowledge_system_dao, 'get', AsyncMock(return_value=SimpleNamespace(id=3)))
    monkeypatch.setattr(service_module.knowledge_point_dao, 'get_all', AsyncMock(return_value=[]))
    get_progress = AsyncMock()
    monkeypatch.setattr(service_module.knowledge_point_dao, 'get_question_counts', get_progress)
    with pytest.raises(errors.NotFoundError):
        asyncio.run(KnowledgeService.get_tree(db=SimpleNamespace(bind=None), user_id=7, system_id=3, root_id=999))
    get_progress.assert_not_awaited()


def test_subtree_sql_keeps_descendants_inside_system_and_stops_at_deleted_points(db: MemorySession) -> None:
    db.connection.exec_driver_sql(
        'CREATE TABLE qbank_v2_knowledge_point (id INTEGER, system_id INTEGER, code TEXT, name TEXT, '
        'parent_id INTEGER, path TEXT, depth INTEGER, sort_order INTEGER, description TEXT, '
        'created_by INTEGER, updated_by INTEGER, created_time DATETIME, updated_time DATETIME, '
        'deleted INTEGER, deleted_time DATETIME)'
    )
    db.connection.exec_driver_sql(
        'INSERT INTO qbank_v2_knowledge_point (id,system_id,parent_id,deleted,depth,sort_order) VALUES '
        '(1,3,NULL,0,0,0),(2,3,1,0,1,0),(3,3,1,0,1,1),(4,3,2,0,2,0),'
        '(5,3,NULL,0,0,1),(6,4,1,0,1,0),(7,3,1,1,1,0),(8,3,7,0,2,0)'
    )
    ids = asyncio.run(knowledge_point_dao.get_all(db, 3, root_id=1))
    assert ids == [1, 2, 3, 4]
    assert asyncio.run(knowledge_point_dao.get_all(db, 3, root_id=6)) == []
